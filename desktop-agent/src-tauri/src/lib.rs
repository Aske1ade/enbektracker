use std::collections::{HashMap, VecDeque};
use std::env;
use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::num::NonZeroUsize;
use std::path::PathBuf;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::thread;
use std::time::Duration;

use chrono::{DateTime, Utc};
use keyring::Entry;
use lru::LruCache;
use parking_lot::Mutex;
use reqwest::{Url, blocking::Client};
use serde::{Deserialize, Serialize};
use tauri::{LogicalSize, Manager, PhysicalPosition, Position};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri_plugin_notification::NotificationExt;

const KEYRING_SERVICE: &str = "tracker-desktop-agent";
const KEYRING_USERNAME: &str = "poll-token";
const LOCAL_API_BASE_URL_PROXY: &str = "http://localhost/api/v1";
const LOCAL_API_BASE_URL_DIRECT: &str = "http://localhost:8888/api/v1";
const LOCAL_WEB_BASE_URL_PROXY: &str = "http://localhost";
const LOCAL_WEB_BASE_URL_DEV: &str = "http://localhost:5173";
const DEFAULT_POLL_LIMIT: usize = 100;
const DEFAULT_POLL_ACTIVE_SECS: u64 = 5;
const DEFAULT_POLL_ERROR_MAX_SECS: u64 = 60;
const DEFAULT_SEEN_CACHE_SIZE: usize = 2048;
const DEFAULT_BIND_TIMEOUT_SECS: i64 = 180;
const DEFAULT_ACTIVITY_LOG_SIZE: usize = 300;
const ACTIVITY_LOG_FILE: &str = "activity-log.json";
#[cfg(target_os = "windows")]
const WINDOWS_TOAST_APP_ID: &str = "com.enbek.tracker";
static BIND_FLOW_COUNTER: AtomicU64 = AtomicU64::new(1);

fn default_api_base_url_proxy() -> &'static str {
    option_env!("ENBEK_AGENT_DEFAULT_API_BASE_URL").unwrap_or(LOCAL_API_BASE_URL_PROXY)
}

fn default_api_base_url_direct() -> &'static str {
    option_env!("ENBEK_AGENT_DEFAULT_API_BASE_URL_DIRECT")
        .or(option_env!("ENBEK_AGENT_DEFAULT_API_BASE_URL"))
        .unwrap_or(LOCAL_API_BASE_URL_DIRECT)
}

fn default_web_base_url_proxy() -> &'static str {
    option_env!("ENBEK_AGENT_DEFAULT_WEB_BASE_URL").unwrap_or(LOCAL_WEB_BASE_URL_PROXY)
}

#[derive(Debug, Clone)]
struct AgentConfig {
    api_base_url: String,
    web_base_url: String,
    poll_limit: usize,
    poll_active_secs: u64,
    poll_error_max_secs: u64,
}

impl AgentConfig {
    fn from_env() -> Self {
        let api_base_url = env::var("TRACKER_AGENT_API_BASE_URL")
            .ok()
            .map(normalize_base_url)
            .unwrap_or_else(detect_api_base_url);
        let web_base_url = env::var("TRACKER_AGENT_WEB_BASE_URL")
            .ok()
            .map(normalize_base_url)
            .unwrap_or_else(|| detect_web_base_url(&api_base_url));
        let poll_limit = env::var("TRACKER_AGENT_POLL_LIMIT")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .filter(|value| (1..=200).contains(value))
            .unwrap_or(DEFAULT_POLL_LIMIT);
        let poll_active_secs = env::var("TRACKER_AGENT_POLL_ACTIVE_SECS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .filter(|value| *value >= 1)
            .unwrap_or(DEFAULT_POLL_ACTIVE_SECS);
        let poll_error_max_secs = env::var("TRACKER_AGENT_POLL_ERROR_MAX_SECS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .filter(|value| *value >= poll_active_secs)
            .unwrap_or(DEFAULT_POLL_ERROR_MAX_SECS);

        Self {
            api_base_url,
            web_base_url,
            poll_limit,
            poll_active_secs,
            poll_error_max_secs,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
struct AgentConfigPublic {
    api_base_url: String,
    web_base_url: String,
    poll_limit: usize,
    poll_active_secs: u64,
    poll_error_max_secs: u64,
}

#[derive(Debug, Clone, Serialize)]
struct DiagnosticsSnapshot {
    last_poll_time: Option<String>,
    cursor: Option<i64>,
    auth_status: String,
    last_error: Option<String>,
    snoozed_until: Option<String>,
    seen_cache_size: usize,
    bound_user_full_name: Option<String>,
    bound_user_email: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ActivityLogEntry {
    at: String,
    level: String,
    source: String,
    message: String,
}

#[derive(Debug, Deserialize)]
struct DesktopEventsPollResponse {
    data: Vec<DesktopEventPayload>,
    next_cursor: Option<i64>,
    has_more: bool,
    server_time: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
struct DesktopEventPayload {
    id: i64,
    event_type: String,
    title: String,
    message: String,
    deeplink: Option<String>,
    task_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
struct BindTokenPayload {
    token: String,
}

#[derive(Debug, Deserialize)]
struct CurrentUserProfilePayload {
    email: String,
    full_name: Option<String>,
}

#[derive(Clone)]
struct AgentState {
    inner: Arc<AgentStateInner>,
}

struct AgentStateInner {
    config: AgentConfig,
    http_client: Client,
    token_cache: Mutex<Option<String>>,
    cursor: Mutex<Option<i64>>,
    seen_ids: Mutex<LruCache<i64, ()>>,
    activity_log: Mutex<VecDeque<ActivityLogEntry>>,
    activity_log_path: PathBuf,
    snoozed_until: Mutex<Option<DateTime<Utc>>>,
    diagnostics: Mutex<DiagnosticsSnapshot>,
    stop: AtomicBool,
    binding_active: AtomicBool,
}

fn resolve_activity_log_path() -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        let base = env::var("LOCALAPPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|_| env::temp_dir());
        return base.join("EnbekTracker").join(ACTIVITY_LOG_FILE);
    }
    #[cfg(not(target_os = "windows"))]
    {
        env::temp_dir()
            .join("enbektracker")
            .join(ACTIVITY_LOG_FILE)
    }
}

fn load_activity_log(path: &PathBuf) -> VecDeque<ActivityLogEntry> {
    if let Ok(raw) = fs::read_to_string(path) {
        if let Ok(entries) = serde_json::from_str::<Vec<ActivityLogEntry>>(&raw) {
            let mut deque = VecDeque::new();
            for entry in entries {
                deque.push_back(entry);
            }
            while deque.len() > DEFAULT_ACTIVITY_LOG_SIZE {
                deque.pop_back();
            }
            return deque;
        }
    }
    VecDeque::new()
}

impl AgentState {
    fn new(config: AgentConfig) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(10))
            .build()
            .expect("failed to initialize HTTP client");
        let activity_log_path = resolve_activity_log_path();
        let activity_log = load_activity_log(&activity_log_path);

        let diagnostics = DiagnosticsSnapshot {
            last_poll_time: None,
            cursor: None,
            auth_status: "missing_token".to_string(),
            last_error: None,
            snoozed_until: None,
            seen_cache_size: 0,
            bound_user_full_name: None,
            bound_user_email: None,
        };

        let cache_size = NonZeroUsize::new(DEFAULT_SEEN_CACHE_SIZE)
            .expect("seen cache size must be non-zero");

        let state = Self {
            inner: Arc::new(AgentStateInner {
                config,
                http_client: client,
                token_cache: Mutex::new(None),
                cursor: Mutex::new(None),
                seen_ids: Mutex::new(LruCache::new(cache_size)),
                activity_log: Mutex::new(activity_log),
                activity_log_path,
                snoozed_until: Mutex::new(None),
                diagnostics: Mutex::new(diagnostics),
                stop: AtomicBool::new(false),
                binding_active: AtomicBool::new(false),
            }),
        };

        state.push_log(
            "info",
            "agent",
            format!(
                "Агент запущен. API={}, WEB={}",
                state.inner.config.api_base_url, state.inner.config.web_base_url
            ),
        );
        match state.read_token() {
            Ok(Some(token)) if !token.trim().is_empty() => {
                state.update_auth_status("authenticated");
                state.push_log(
                    "info",
                    "auth",
                    "Найден сохраненный токен в защищенном хранилище".to_string(),
                );
                match fetch_current_user_profile(&state, &token) {
                    Ok(profile) => {
                        let display = profile
                            .full_name
                            .clone()
                            .unwrap_or_else(|| profile.email.clone());
                        state.set_bound_user_profile(profile.full_name, Some(profile.email));
                        state.push_log("info", "auth", format!("Привязан аккаунт: {display}"));
                    }
                    Err(err) => {
                        state.clear_bound_user_profile();
                        state.push_log(
                            "warn",
                            "auth",
                            format!("Не удалось получить профиль привязанного аккаунта: {}", err),
                        );
                    }
                }
            }
            Ok(_) => {}
            Err(err) => {
                state.push_log(
                    "warn",
                    "auth",
                    format!("Не удалось прочитать токен из хранилища: {}", err),
                );
            }
        }
        state
    }

    fn config_public(&self) -> AgentConfigPublic {
        AgentConfigPublic {
            api_base_url: self.inner.config.api_base_url.clone(),
            web_base_url: self.inner.config.web_base_url.clone(),
            poll_limit: self.inner.config.poll_limit,
            poll_active_secs: self.inner.config.poll_active_secs,
            poll_error_max_secs: self.inner.config.poll_error_max_secs,
        }
    }

    fn persist_activity_log(&self) {
        let entries: Vec<ActivityLogEntry> = self.inner.activity_log.lock().iter().cloned().collect();
        if let Some(parent) = self.inner.activity_log_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(serialized) = serde_json::to_string(&entries) {
            let _ = fs::write(&self.inner.activity_log_path, serialized);
        }
    }

    fn push_log(&self, level: &str, source: &str, message: String) {
        {
            let mut log = self.inner.activity_log.lock();
            log.push_front(ActivityLogEntry {
                at: Utc::now().to_rfc3339(),
                level: level.to_string(),
                source: source.to_string(),
                message,
            });
            while log.len() > DEFAULT_ACTIVITY_LOG_SIZE {
                log.pop_back();
            }
        }
        self.persist_activity_log();
    }

    fn activity_log(&self) -> Vec<ActivityLogEntry> {
        self.inner.activity_log.lock().iter().cloned().collect()
    }

    fn clear_activity_log(&self) {
        self.inner.activity_log.lock().clear();
        self.push_log("info", "agent", "Журнал агента очищен".to_string());
    }

    fn read_token(&self) -> Result<Option<String>, String> {
        if let Some(token) = self.inner.token_cache.lock().clone() {
            return Ok(Some(token));
        }
        let entry = Entry::new(KEYRING_SERVICE, KEYRING_USERNAME).map_err(|err| err.to_string())?;
        match entry.get_password() {
            Ok(token) => {
                *self.inner.token_cache.lock() = Some(token.clone());
                Ok(Some(token))
            }
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(err) => Err(err.to_string()),
        }
    }

    fn save_token(&self, token: String) -> Result<(), String> {
        let entry = Entry::new(KEYRING_SERVICE, KEYRING_USERNAME).map_err(|err| err.to_string())?;
        let token_for_profile = token.clone();
        entry.set_password(&token).map_err(|err| err.to_string())?;
        *self.inner.token_cache.lock() = Some(token);
        self.update_auth_status("authenticated");
        self.clear_error();
        self.push_log(
            "info",
            "auth",
            "Токен успешно сохранен в защищенном хранилище".to_string(),
        );
        match fetch_current_user_profile(self, &token_for_profile) {
            Ok(profile) => {
                let display = profile
                    .full_name
                    .clone()
                    .unwrap_or_else(|| profile.email.clone());
                self.set_bound_user_profile(profile.full_name, Some(profile.email));
                self.push_log("info", "auth", format!("Привязан аккаунт: {display}"));
            }
            Err(err) => {
                self.clear_bound_user_profile();
                self.push_log(
                    "warn",
                    "auth",
                    format!("Не удалось получить профиль привязанного аккаунта: {}", err),
                );
            }
        }
        Ok(())
    }

    fn clear_token(&self) -> Result<(), String> {
        let entry = Entry::new(KEYRING_SERVICE, KEYRING_USERNAME).map_err(|err| err.to_string())?;
        match entry.delete_credential() {
            Ok(()) => {}
            Err(keyring::Error::NoEntry) => {}
            Err(err) => return Err(err.to_string()),
        }
        *self.inner.token_cache.lock() = None;
        self.reset_runtime_delivery_state();
        self.update_auth_status("missing_token");
        self.clear_bound_user_profile();
        self.push_log("warn", "auth", "Токен удален".to_string());
        Ok(())
    }

    fn reset_runtime_delivery_state(&self) {
        *self.inner.cursor.lock() = None;
        let seen_cache_size = {
            let mut seen = self.inner.seen_ids.lock();
            seen.clear();
            seen.len()
        };
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.cursor = None;
        diagnostics.seen_cache_size = seen_cache_size;
    }

    fn set_cursor(&self, cursor: Option<i64>) {
        *self.inner.cursor.lock() = cursor;
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.cursor = cursor;
    }

    fn cursor(&self) -> Option<i64> {
        *self.inner.cursor.lock()
    }

    fn set_snooze_minutes(&self, minutes: u64) {
        let snoozed_until = if minutes == 0 {
            None
        } else {
            Some(Utc::now() + chrono::Duration::minutes(minutes as i64))
        };
        *self.inner.snoozed_until.lock() = snoozed_until;
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.snoozed_until = snoozed_until.map(|value| value.to_rfc3339());
        drop(diagnostics);
        if minutes == 0 {
            self.push_log("info", "notify", "Пауза уведомлений снята".to_string());
        } else {
            self.push_log(
                "info",
                "notify",
                format!("Уведомления поставлены на паузу на {} мин", minutes),
            );
        }
    }

    fn is_snoozed(&self) -> bool {
        let now = Utc::now();
        let mut guard = self.inner.snoozed_until.lock();
        match *guard {
            Some(until) if until > now => true,
            Some(_) => {
                *guard = None;
                let mut diagnostics = self.inner.diagnostics.lock();
                diagnostics.snoozed_until = None;
                false
            }
            None => false,
        }
    }

    fn mark_event_seen(&self, event_id: i64) -> bool {
        let mut seen = self.inner.seen_ids.lock();
        if seen.contains(&event_id) {
            return false;
        }
        seen.put(event_id, ());
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.seen_cache_size = seen.len();
        true
    }

    fn set_poll_success(&self, cursor: Option<i64>) {
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.last_poll_time = Some(Utc::now().to_rfc3339());
        diagnostics.cursor = cursor;
        diagnostics.auth_status = "authenticated".to_string();
        diagnostics.last_error = None;
    }

    fn set_poll_error(&self, error: &str) {
        let mut diagnostics = self.inner.diagnostics.lock();
        let should_log = diagnostics.last_error.as_deref() != Some(error);
        diagnostics.last_poll_time = Some(Utc::now().to_rfc3339());
        diagnostics.last_error = Some(error.to_string());
        diagnostics.auth_status = if error.contains("missing token") {
            diagnostics.bound_user_full_name = None;
            diagnostics.bound_user_email = None;
            "missing_token".to_string()
        } else {
            "error".to_string()
        };
        drop(diagnostics);
        if should_log {
            self.push_log("error", "poll", error.to_string());
        }
    }

    fn update_auth_status(&self, status: &str) {
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.auth_status = status.to_string();
    }

    fn clear_error(&self) {
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.last_error = None;
    }

    fn set_bound_user_profile(&self, full_name: Option<String>, email: Option<String>) {
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.bound_user_full_name = full_name;
        diagnostics.bound_user_email = email;
    }

    fn clear_bound_user_profile(&self) {
        let mut diagnostics = self.inner.diagnostics.lock();
        diagnostics.bound_user_full_name = None;
        diagnostics.bound_user_email = None;
    }

    fn diagnostics(&self) -> DiagnosticsSnapshot {
        self.inner.diagnostics.lock().clone()
    }

    fn base_web_url(&self) -> String {
        self.inner.config.web_base_url.clone()
    }

    fn stop(&self) {
        self.inner.stop.store(true, Ordering::Relaxed);
        self.push_log("info", "agent", "Остановка агента".to_string());
    }

    fn begin_binding(&self) -> bool {
        let started = !self.inner.binding_active.swap(true, Ordering::SeqCst);
        if started {
            self.push_log("info", "bind", "Запущен процесс привязки аккаунта".to_string());
        }
        started
    }

    fn finish_binding(&self) {
        self.inner.binding_active.store(false, Ordering::SeqCst);
        self.push_log("info", "bind", "Процесс привязки завершен".to_string());
    }
}

fn normalize_base_url(value: String) -> String {
    value.trim_end_matches('/').to_string()
}

fn is_http_ok(url: &str) -> bool {
    let client = match Client::builder().timeout(Duration::from_millis(900)).build() {
        Ok(value) => value,
        Err(_) => return false,
    };
    match client.get(url).send() {
        Ok(response) => response.status().is_success(),
        Err(_) => false,
    }
}

fn detect_api_base_url() -> String {
    let candidates = [default_api_base_url_proxy(), default_api_base_url_direct()];
    for candidate in candidates {
        let health_url = format!(
            "{}/utils/health-check/",
            normalize_base_url(candidate.to_string())
        );
        if is_http_ok(&health_url) {
            return normalize_base_url(candidate.to_string());
        }
    }
    normalize_base_url(default_api_base_url_direct().to_string())
}

fn detect_web_base_url(api_base_url: &str) -> String {
    let configured_web = normalize_base_url(default_web_base_url_proxy().to_string());
    if configured_web != normalize_base_url(LOCAL_WEB_BASE_URL_PROXY.to_string()) {
        return configured_web;
    }
    if let Some(inferred) = infer_web_base_url_from_api(api_base_url) {
        return inferred;
    }
    if api_base_url.contains(":8888") && is_http_ok(LOCAL_WEB_BASE_URL_DEV) {
        return normalize_base_url(LOCAL_WEB_BASE_URL_DEV.to_string());
    }
    if is_http_ok(LOCAL_WEB_BASE_URL_PROXY) {
        return normalize_base_url(LOCAL_WEB_BASE_URL_PROXY.to_string());
    }
    if api_base_url.contains(":8888") {
        return normalize_base_url(LOCAL_WEB_BASE_URL_DEV.to_string());
    }
    normalize_base_url(LOCAL_WEB_BASE_URL_PROXY.to_string())
}

fn infer_web_base_url_from_api(api_base_url: &str) -> Option<String> {
    let parsed = Url::parse(api_base_url).ok()?;
    let host = parsed.host_str()?.to_string();
    let is_local_host = matches!(host.as_str(), "localhost" | "127.0.0.1" | "::1");

    if is_local_host && parsed.port_or_known_default() == Some(8888) {
        return None;
    }

    let scheme = parsed.scheme().to_string();
    let default_port = match scheme.as_str() {
        "http" => 80,
        "https" => 443,
        _ => 0,
    };
    let authority = match parsed.port() {
        Some(port) if port != default_port => format!("{host}:{port}"),
        _ => host,
    };
    Some(format!("{scheme}://{authority}"))
}

fn ensure_leading_slash(value: &str) -> String {
    if value.starts_with('/') {
        value.to_string()
    } else {
        format!("/{value}")
    }
}

fn build_deeplink(config: &AgentConfig, event: &DesktopEventPayload) -> String {
    if let Some(deeplink) = event.deeplink.as_ref() {
        if deeplink.starts_with("http://") || deeplink.starts_with("https://") {
            return deeplink.to_string();
        }
        return format!("{}{}", config.web_base_url, ensure_leading_slash(deeplink));
    }

    if let Some(task_id) = event.task_id {
        return format!("{}/tasks/{task_id}", config.web_base_url);
    }

    config.web_base_url.clone()
}

fn create_bind_state() -> String {
    let counter = BIND_FLOW_COUNTER.fetch_add(1, Ordering::Relaxed);
    format!("bind-{}-{counter}", Utc::now().timestamp_millis())
}

fn parse_query(query: &str) -> HashMap<String, String> {
    let mut values = HashMap::new();
    for pair in query.split('&') {
        if pair.is_empty() {
            continue;
        }
        let mut parts = pair.splitn(2, '=');
        let key = parts.next().unwrap_or_default().to_string();
        let value = parts.next().unwrap_or_default().to_string();
        values.insert(key, value);
    }
    values
}

fn find_header_end(buffer: &[u8]) -> Option<usize> {
    buffer
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .map(|idx| idx + 4)
}

fn write_http_json_response(
    stream: &mut TcpStream,
    status_line: &str,
    payload: &str,
) -> Result<(), String> {
    let response = format!(
        "HTTP/1.1 {status_line}\r\n\
         Content-Type: application/json; charset=utf-8\r\n\
         Access-Control-Allow-Origin: *\r\n\
         Access-Control-Allow-Methods: POST, OPTIONS\r\n\
         Access-Control-Allow-Headers: Content-Type\r\n\
         Content-Length: {}\r\n\
         Connection: close\r\n\r\n\
         {payload}",
        payload.as_bytes().len()
    );
    stream
        .write_all(response.as_bytes())
        .map_err(|err| err.to_string())?;
    stream.flush().map_err(|err| err.to_string())
}

fn read_http_request(
    stream: &mut TcpStream,
) -> Result<(String, String, HashMap<String, String>, Vec<u8>), String> {
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|err| err.to_string())?;

    let mut buffer: Vec<u8> = Vec::new();
    let mut chunk = [0_u8; 2048];
    let mut header_end: Option<usize> = None;
    let mut expected_total_len: Option<usize> = None;

    loop {
        let read_count = stream.read(&mut chunk).map_err(|err| err.to_string())?;
        if read_count == 0 {
            break;
        }
        buffer.extend_from_slice(&chunk[..read_count]);

        if header_end.is_none() {
            if let Some(end) = find_header_end(&buffer) {
                header_end = Some(end);
                let headers_raw = String::from_utf8_lossy(&buffer[..end]);
                let content_length = headers_raw
                    .lines()
                    .find_map(|line| {
                        let mut parts = line.splitn(2, ':');
                        let key = parts.next()?.trim().to_lowercase();
                        let value = parts.next()?.trim();
                        if key == "content-length" {
                            return value.parse::<usize>().ok();
                        }
                        None
                    })
                    .unwrap_or(0);
                expected_total_len = Some(end + content_length);
            }
        }

        if let Some(total_len) = expected_total_len {
            if buffer.len() >= total_len {
                break;
            }
        }

        if buffer.len() > 1024 * 1024 {
            return Err("request too large".to_string());
        }
    }

    let end = header_end.ok_or_else(|| "invalid http request".to_string())?;
    let headers_raw = String::from_utf8_lossy(&buffer[..end]).to_string();
    let mut lines = headers_raw.lines();
    let request_line = lines
        .next()
        .ok_or_else(|| "missing request line".to_string())?;
    let mut request_parts = request_line.split_whitespace();
    let method = request_parts
        .next()
        .ok_or_else(|| "missing method".to_string())?
        .to_string();
    let target = request_parts
        .next()
        .ok_or_else(|| "missing request target".to_string())?;

    let (path, query) = if let Some((path_part, query_part)) = target.split_once('?') {
        (path_part.to_string(), parse_query(query_part))
    } else {
        (target.to_string(), HashMap::new())
    };

    let body = buffer[end..].to_vec();
    Ok((method, path, query, body))
}

fn process_binding_request(
    state: &AgentState,
    expected_state: &str,
    stream: &mut TcpStream,
) -> Result<bool, String> {
    let (method, path, query, body) = read_http_request(stream)?;
    state.push_log(
        "info",
        "bind",
        format!("Входящий запрос привязки: method={} path={}", method, path),
    );

    if method == "OPTIONS" {
        write_http_json_response(stream, "204 No Content", "{}")?;
        return Ok(false);
    }

    if method != "POST" {
        write_http_json_response(
            stream,
            "405 Method Not Allowed",
            r#"{"ok":false,"error":"method_not_allowed"}"#,
        )?;
        state.push_log("warn", "bind", "Отклонен запрос: method_not_allowed".to_string());
        return Ok(false);
    }

    if path != "/callback" {
        write_http_json_response(
            stream,
            "404 Not Found",
            r#"{"ok":false,"error":"not_found"}"#,
        )?;
        state.push_log("warn", "bind", "Отклонен запрос: not_found".to_string());
        return Ok(false);
    }

    let provided_state = query.get("state").cloned().unwrap_or_default();
    if provided_state != expected_state {
        write_http_json_response(
            stream,
            "400 Bad Request",
            r#"{"ok":false,"error":"invalid_state"}"#,
        )?;
        state.push_log("warn", "bind", "Отклонен запрос: invalid_state".to_string());
        return Ok(false);
    }

    let payload = serde_json::from_slice::<BindTokenPayload>(&body)
        .map_err(|_| "invalid bind payload".to_string())?;
    let token = payload.token.trim();
    if token.is_empty() {
        write_http_json_response(
            stream,
            "400 Bad Request",
            r#"{"ok":false,"error":"empty_token"}"#,
        )?;
        state.push_log("warn", "bind", "Отклонен запрос: empty_token".to_string());
        return Ok(false);
    }

    state.save_token(token.to_string())?;
    state.reset_runtime_delivery_state();
    match bootstrap_cursor_without_delivery(state) {
        Ok(cursor) => {
            state.push_log(
                "info",
                "bind",
                format!(
                    "Курсор инициализирован: {}. Старые события пропущены",
                    cursor
                        .map(|value| value.to_string())
                        .unwrap_or_else(|| "null".to_string())
                ),
            );
        }
        Err(err) => {
            state.push_log(
                "warn",
                "bind",
                format!("Не удалось инициализировать курсор после привязки: {}", err),
            );
        }
    }
    write_http_json_response(stream, "200 OK", r#"{"ok":true,"linked":true}"#)?;
    state.push_log("info", "bind", "Аккаунт успешно привязан".to_string());
    Ok(true)
}

fn spawn_binding_listener(state: AgentState, listener: TcpListener, expected_state: String) {
    thread::spawn(move || {
        let _ = listener.set_nonblocking(true);
        let started_at = Utc::now();

        loop {
            if state.inner.stop.load(Ordering::Relaxed) {
                break;
            }

            if Utc::now()
                .signed_duration_since(started_at)
                .num_seconds()
                >= DEFAULT_BIND_TIMEOUT_SECS
            {
                if let Ok(Some(token)) = state.read_token() {
                    if token.trim().is_empty() {
                        state.update_auth_status("missing_token");
                    } else {
                        state.update_auth_status("authenticated");
                    }
                } else {
                    state.update_auth_status("missing_token");
                }
                state.set_poll_error("binding timeout");
                state.push_log(
                    "warn",
                    "bind",
                    "Привязка завершилась по таймауту (180 сек)".to_string(),
                );
                break;
            }

            match listener.accept() {
                Ok((mut stream, _addr)) => match process_binding_request(&state, &expected_state, &mut stream) {
                    Ok(true) => {
                        state.clear_error();
                        break;
                    }
                    Ok(false) => {}
                    Err(err) => {
                        state.set_poll_error(&err);
                        state.push_log("error", "bind", format!("Ошибка привязки: {}", err));
                    }
                },
                Err(err) if err.kind() == std::io::ErrorKind::WouldBlock => {
                    thread::sleep(Duration::from_millis(120));
                }
                Err(err) => {
                    state.set_poll_error(&format!("binding listener error: {err}"));
                    state.push_log(
                        "error",
                        "bind",
                        format!("Ошибка binding-listener: {}", err),
                    );
                    break;
                }
            }
        }

        state.finish_binding();
    });
}

fn start_account_binding_flow(state: &AgentState) -> Result<String, String> {
    if !state.begin_binding() {
        state.push_log("warn", "bind", "Привязка уже выполняется".to_string());
        return Err("Привязка уже выполняется".to_string());
    }

    let listener = match TcpListener::bind("127.0.0.1:0") {
        Ok(listener) => listener,
        Err(err) => {
            state.finish_binding();
            state.push_log(
                "error",
                "bind",
                format!("Не удалось открыть локальный порт для привязки: {}", err),
            );
            return Err(format!("Не удалось открыть локальный порт: {err}"));
        }
    };
    let port = listener
        .local_addr()
        .map_err(|err| err.to_string())?
        .port();
    let bind_state = create_bind_state();
    let bind_url = format!(
        "{}/desktop-agent-bind?state={}&port={}",
        state.base_web_url(),
        bind_state,
        port
    );

    if let Err(err) = webbrowser::open(&bind_url) {
        state.finish_binding();
        state.push_log("error", "bind", format!("Не удалось открыть браузер: {}", err));
        return Err(format!("Не удалось открыть браузер: {err}"));
    }

    state.update_auth_status("binding_pending");
    state.clear_error();
    state.push_log(
        "info",
        "bind",
        "Открыт URL привязки в браузере".to_string(),
    );
    spawn_binding_listener(state.clone(), listener, bind_state);
    Ok(bind_url)
}

fn poll_once(state: &AgentState) -> Result<DesktopEventsPollResponse, String> {
    let token = match state.read_token()? {
        Some(value) if !value.trim().is_empty() => value,
        _ => return Err("missing token".to_string()),
    };

    poll_with_cursor(
        state,
        &token,
        state.cursor(),
        state.inner.config.poll_limit,
    )
}

fn poll_with_cursor(
    state: &AgentState,
    token: &str,
    cursor: Option<i64>,
    limit: usize,
) -> Result<DesktopEventsPollResponse, String> {
    let mut last_error: Option<String> = None;
    for api_base_url in candidate_api_base_urls(&state.inner.config.api_base_url) {
        let mut request = state
            .inner
            .http_client
            .get(format!("{api_base_url}/desktop-events/poll"))
            .query(&[("limit", limit)])
            .bearer_auth(token);

        if let Some(cursor) = cursor {
            request = request.query(&[("cursor", cursor)]);
        }

        match request.send() {
            Ok(response) => {
                let status = response.status();
                if !status.is_success() {
                    last_error = Some(format!("poll failed with HTTP {status}"));
                    continue;
                }
                return response
                    .json::<DesktopEventsPollResponse>()
                    .map_err(|err| err.to_string());
            }
            Err(err) => {
                last_error = Some(err.to_string());
            }
        }
    }

    Err(last_error.unwrap_or_else(|| "poll failed".to_string()))
}

fn fetch_current_user_profile(
    state: &AgentState,
    token: &str,
) -> Result<CurrentUserProfilePayload, String> {
    let mut last_error: Option<String> = None;
    for api_base_url in candidate_api_base_urls(&state.inner.config.api_base_url) {
        match state
            .inner
            .http_client
            .get(format!("{api_base_url}/users/me"))
            .bearer_auth(token)
            .send()
        {
            Ok(response) => {
                let status = response.status();
                if !status.is_success() {
                    last_error = Some(format!("profile request failed with HTTP {status}"));
                    continue;
                }
                return response
                    .json::<CurrentUserProfilePayload>()
                    .map_err(|err| err.to_string());
            }
            Err(err) => {
                last_error = Some(err.to_string());
            }
        }
    }
    Err(last_error.unwrap_or_else(|| "profile request failed".to_string()))
}

fn candidate_api_base_urls(primary: &str) -> Vec<String> {
    let normalized_primary = normalize_base_url(primary.to_string());
    let normalized_proxy = normalize_base_url(default_api_base_url_proxy().to_string());
    let normalized_direct = normalize_base_url(default_api_base_url_direct().to_string());

    let mut values = Vec::new();
    values.push(normalized_primary.clone());

    if normalized_primary == normalized_proxy {
        values.push(normalized_direct);
    } else if normalized_primary == normalized_direct {
        values.push(normalized_proxy);
    } else {
        values.push(normalized_proxy);
        values.push(normalized_direct);
    }

    let mut ordered_unique = Vec::new();
    for value in values {
        if !ordered_unique.iter().any(|item| item == &value) {
            ordered_unique.push(value);
        }
    }
    ordered_unique
}

fn bootstrap_cursor_without_delivery(state: &AgentState) -> Result<Option<i64>, String> {
    let token = match state.read_token()? {
        Some(value) if !value.trim().is_empty() => value,
        _ => return Ok(None),
    };

    let mut cursor: Option<i64> = None;
    let mut iterations = 0_u16;

    loop {
        iterations = iterations.saturating_add(1);
        if iterations > 1000 {
            break;
        }
        let payload = poll_with_cursor(state, &token, cursor, 200)?;
        cursor = payload.next_cursor.or(cursor);
        if !payload.has_more {
            break;
        }
        if payload.data.is_empty() {
            break;
        }
    }

    state.set_cursor(cursor);
    state.set_poll_success(cursor);
    Ok(cursor)
}

fn spawn_poller(app: tauri::AppHandle, state: AgentState) {
    thread::spawn(move || {
        let mut delay_secs = state.inner.config.poll_active_secs;
        loop {
            if state.inner.stop.load(Ordering::Relaxed) {
                break;
            }

            if state.inner.binding_active.load(Ordering::Relaxed) {
                thread::sleep(Duration::from_millis(250));
                continue;
            }

            match poll_once(&state) {
                Ok(payload) => {
                    let mut next_delay = state.inner.config.poll_active_secs;
                    if payload.server_time.is_some() {
                        state.clear_error();
                    }
                    if payload.has_more {
                        next_delay = 1;
                    }
                    let next_cursor = payload.next_cursor.or_else(|| state.cursor());
                    state.set_cursor(next_cursor);
                    state.set_poll_success(next_cursor);

                    let mut delivered_count = 0_u64;
                    let mut duplicate_count = 0_u64;
                    let mut snoozed_count = 0_u64;

                    for event in payload.data {
                        if !state.mark_event_seen(event.id) {
                            duplicate_count += 1;
                            continue;
                        }
                        if state.is_snoozed() {
                            snoozed_count += 1;
                            continue;
                        }

                        let deeplink = build_deeplink(&state.inner.config, &event);
                        show_notification(&app, &event, &deeplink);
                        delivered_count += 1;
                        state.push_log(
                            "info",
                            "notify",
                            format!(
                                "#{} [{}] {}",
                                event.id, event.event_type, event.title
                            ),
                        );
                    }

                    if duplicate_count > 0 || snoozed_count > 0 {
                        state.push_log(
                            "info",
                            "poll",
                            format!(
                                "Результат poll: delivered={}, duplicates={}, snoozed={}",
                                delivered_count, duplicate_count, snoozed_count
                            ),
                        );
                    }

                    delay_secs = next_delay;
                }
                Err(err) => {
                    state.set_poll_error(&err);
                    delay_secs = (delay_secs.saturating_mul(2)).min(state.inner.config.poll_error_max_secs);
                }
            }

            thread::sleep(Duration::from_secs(delay_secs));
        }
    });
}

fn event_type_label_ru(event_type: &str) -> &str {
    match event_type {
        "assign" => "Назначение",
        "due_soon" => "Срок скоро",
        "overdue" => "Просрочено",
        "status_changed" => "Статус изменен",
        "close_requested" => "Запрос на закрытие",
        "close_approved" => "Закрытие подтверждено",
        "comment_added" => "Новый комментарий",
        "system" => "Системное",
        _ => event_type,
    }
}

#[cfg(target_os = "windows")]
fn show_notification(
    app: &tauri::AppHandle,
    event: &DesktopEventPayload,
    deeplink: &str,
) {
    use tauri_winrt_notification::Toast;

    let launch_url = deeplink.to_string();
    let fallback_url = deeplink.to_string();
    let event_label = event_type_label_ru(&event.event_type);
    let show_result = Toast::new(WINDOWS_TOAST_APP_ID)
        .title(&event.title)
        .text1(&format!("[{}] {}", event_label, event.message))
        .on_activated(move |_| {
            let _ = webbrowser::open(&launch_url);
            Ok(())
        })
        .show();

    if show_result.is_err() {
        let _ = app
            .notification()
            .builder()
            .title(&event.title)
            .body(&event.message)
            .show();
        let _ = webbrowser::open(&fallback_url);
    }
}

#[cfg(not(target_os = "windows"))]
fn show_notification(
    app: &tauri::AppHandle,
    event: &DesktopEventPayload,
    _deeplink: &str,
) {
    let event_label = event_type_label_ru(&event.event_type);
    let _ = app
        .notification()
        .builder()
        .title(&event.title)
        .body(&format!("[{}] {}", event_label, event.message))
        .show();
}

fn show_diagnostics_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let width = 420_i32;
        let height = 500_i32;
        let _ = window.set_size(LogicalSize::new(width as f64, height as f64));
        if let Ok(Some(monitor)) = window.current_monitor() {
            let monitor_pos = monitor.position();
            let monitor_size = monitor.size();
            let x = monitor_pos.x + monitor_size.width as i32 - width - 16;
            let y = monitor_pos.y + monitor_size.height as i32 - height - 56;
            let safe_x = x.max(monitor_pos.x);
            let safe_y = y.max(monitor_pos.y);
            let _ = window.set_position(Position::Physical(PhysicalPosition::new(safe_x, safe_y)));
        }
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn hide_diagnostics_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

fn create_tray(app: &tauri::AppHandle) -> tauri::Result<()> {
    let open_tracker = MenuItem::with_id(app, "open_tracker", "Открыть EnbekTracker", true, None::<&str>)?;
    let bind_account = MenuItem::with_id(app, "bind_account", "Привязать аккаунт", true, None::<&str>)?;
    let diagnostics = MenuItem::with_id(app, "show_diagnostics", "Диагностика агента", true, None::<&str>)?;
    let snooze_15 = MenuItem::with_id(app, "snooze_15", "Пауза уведомлений на 15 мин", true, None::<&str>)?;
    let snooze_60 = MenuItem::with_id(app, "snooze_60", "Пауза уведомлений на 60 мин", true, None::<&str>)?;
    let resume = MenuItem::with_id(app, "resume", "Возобновить уведомления", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Выход", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;

    let menu = Menu::with_items(
        app,
        &[
            &open_tracker,
            &bind_account,
            &diagnostics,
            &separator,
            &snooze_15,
            &snooze_60,
            &resume,
            &separator,
            &quit,
        ],
    )?;

    let icon = app.default_window_icon().cloned();
    let mut builder = TrayIconBuilder::new().menu(&menu).show_menu_on_left_click(false);
    if let Some(icon) = icon {
        builder = builder.icon(icon);
    }

    builder
        .on_menu_event(|app, event| {
            let state = app.state::<AgentState>();
            match event.id().as_ref() {
                "open_tracker" => {
                    let _ = webbrowser::open(&state.base_web_url());
                    state.push_log("info", "ui", "Открыт EnbekTracker из трея".to_string());
                }
                "bind_account" => {
                    let has_token = state
                        .read_token()
                        .ok()
                        .flatten()
                        .map(|value| !value.trim().is_empty())
                        .unwrap_or(false);
                    if has_token {
                        let _ = state.clear_token();
                        state.push_log("info", "auth", "Выход из аккаунта через трей".to_string());
                    } else {
                        let _ = start_account_binding_flow(&state);
                    }
                    show_diagnostics_window(app);
                }
                "show_diagnostics" => show_diagnostics_window(app),
                "snooze_15" => state.set_snooze_minutes(15),
                "snooze_60" => state.set_snooze_minutes(60),
                "resume" => state.set_snooze_minutes(0),
                "quit" => {
                    state.stop();
                    app.exit(0);
                }
                _ => {}
            }
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_diagnostics_window(tray.app_handle());
            }
        })
        .build(app)?;

    Ok(())
}

#[cfg(target_os = "windows")]
fn ensure_windows_autostart() {
    let app_data = match env::var("APPDATA") {
        Ok(value) => value,
        Err(_) => return,
    };
    let startup_dir = PathBuf::from(app_data)
        .join("Microsoft")
        .join("Windows")
        .join("Start Menu")
        .join("Programs")
        .join("Startup");
    let exe_path = match env::current_exe() {
        Ok(value) => value,
        Err(_) => return,
    };
    let launcher = startup_dir.join("TrackerDesktopAgent.cmd");
    let script = format!("@echo off\r\nstart \"\" \"{}\"\r\n", exe_path.display());
    let _ = std::fs::write(launcher, script);
}

#[cfg(not(target_os = "windows"))]
fn ensure_windows_autostart() {}

#[tauri::command]
fn get_diagnostics(state: tauri::State<'_, AgentState>) -> DiagnosticsSnapshot {
    state.diagnostics()
}

#[tauri::command]
fn get_agent_config(state: tauri::State<'_, AgentState>) -> AgentConfigPublic {
    state.config_public()
}

#[tauri::command]
fn get_activity_log(state: tauri::State<'_, AgentState>) -> Vec<ActivityLogEntry> {
    state.activity_log()
}

#[tauri::command]
fn clear_activity_log(state: tauri::State<'_, AgentState>) {
    state.clear_activity_log();
}

#[tauri::command]
fn save_auth_token(state: tauri::State<'_, AgentState>, token: String) -> Result<(), String> {
    state.save_token(token)?;
    state.reset_runtime_delivery_state();
    let _ = bootstrap_cursor_without_delivery(&state);
    Ok(())
}

#[tauri::command]
fn clear_auth_token(state: tauri::State<'_, AgentState>) -> Result<(), String> {
    state.clear_token()
}

#[tauri::command]
fn set_snooze_minutes(state: tauri::State<'_, AgentState>, minutes: u64) -> Result<(), String> {
    state.set_snooze_minutes(minutes);
    Ok(())
}

#[tauri::command]
fn open_tracker_now(state: tauri::State<'_, AgentState>) -> Result<(), String> {
    webbrowser::open(&state.base_web_url())
        .map_err(|err| err.to_string())
        .map(|_| ())
}

#[tauri::command]
fn start_account_binding(state: tauri::State<'_, AgentState>) -> Result<String, String> {
    start_account_binding_flow(&state)
}

#[tauri::command]
fn send_test_notification(
    app: tauri::AppHandle,
    state: tauri::State<'_, AgentState>,
) -> Result<(), String> {
    let event = DesktopEventPayload {
        id: 0,
        event_type: "system".to_string(),
        title: "Тест уведомления Windows".to_string(),
        message: "Это тест desktop-уведомлений EnbekTracker агента".to_string(),
        deeplink: Some("/tasks".to_string()),
        task_id: None,
    };
    let deeplink = build_deeplink(&state.inner.config, &event);
    show_notification(&app, &event, &deeplink);
    state.push_log(
        "info",
        "notify",
        "Отправлено локальное тестовое уведомление".to_string(),
    );
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let state = AgentState::new(AgentConfig::from_env());
    let poll_state = state.clone();

    tauri::Builder::default()
        .manage(state)
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![
            get_diagnostics,
            get_agent_config,
            get_activity_log,
            clear_activity_log,
            save_auth_token,
            clear_auth_token,
            set_snooze_minutes,
            open_tracker_now,
            start_account_binding,
            send_test_notification
        ])
        .setup(move |app| {
            ensure_windows_autostart();
            hide_diagnostics_window(&app.handle());
            if let Some(window) = app.get_webview_window("main") {
                let window_for_event = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = window_for_event.hide();
                    }
                });
            }
            create_tray(&app.handle())?;
            spawn_poller(app.handle().clone(), poll_state.clone());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tracker desktop agent");
}
