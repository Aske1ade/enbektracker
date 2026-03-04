import { invoke } from "@tauri-apps/api/core"

type DiagnosticsSnapshot = {
  last_poll_time: string | null
  cursor: number | null
  auth_status: string
  last_error: string | null
  snoozed_until: string | null
  seen_cache_size: number
  bound_user_full_name?: string | null
  bound_user_email?: string | null
}

type AgentConfig = {
  api_base_url: string
  web_base_url: string
  poll_limit: number
  poll_active_secs: number
  poll_error_max_secs: number
}

type ActivityLogEntry = {
  at: string
  level: string
  source: string
  message: string
}

const statusGrid = document.querySelector("#status-grid") as HTMLDListElement
const activityLog = document.querySelector("#activity-log") as HTMLUListElement
const messageEl = document.querySelector("#message") as HTMLParagraphElement
const bindAccountButton = document.querySelector(
  "#bind-account",
) as HTMLButtonElement
const clearTokenButton = document.querySelector(
  "#clear-token",
) as HTMLButtonElement
const snooze15Button = document.querySelector("#snooze-15") as HTMLButtonElement
const snooze60Button = document.querySelector("#snooze-60") as HTMLButtonElement
const resumeButton = document.querySelector("#resume") as HTMLButtonElement
const openTrackerButton = document.querySelector(
  "#open-tracker",
) as HTMLButtonElement
const testToastButton = document.querySelector("#test-toast") as HTMLButtonElement
const clearLogButton = document.querySelector("#clear-log") as HTMLButtonElement

let latestDiagnostics: DiagnosticsSnapshot | null = null

function formatAuthStatus(value: string): string {
  const normalized = value.trim().toLowerCase()
  const labels: Record<string, string> = {
    authenticated: "Токен валиден",
    missing_token: "Токен отсутствует",
    binding_pending: "Ожидание привязки в браузере",
    error: "Ошибка авторизации",
  }
  return labels[normalized] ?? value
}

function formatLastError(value: string | null): string {
  if (!value) return "нет"
  if (value === "missing token") return "токен не привязан"
  if (value === "binding timeout") return "таймаут привязки аккаунта"
  return value
}

function setMessage(value: string): void {
  messageEl.textContent = value
}

function renderAuthActions(diagnostics: DiagnosticsSnapshot): void {
  const authStatus = diagnostics.auth_status.trim().toLowerCase()
  const isAuthenticated = authStatus === "authenticated"
  const isBinding = authStatus === "binding_pending"

  bindAccountButton.disabled = isBinding
  bindAccountButton.classList.toggle("btn-danger", isAuthenticated)
  bindAccountButton.classList.toggle("btn-primary", !isAuthenticated)
  bindAccountButton.textContent = isBinding
    ? "Привязка выполняется..."
    : isAuthenticated
      ? "Выйти из аккаунта"
      : "Привязать аккаунт"

  clearTokenButton.disabled = !isAuthenticated
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

function renderStatus(config: AgentConfig, diagnostics: DiagnosticsSnapshot): void {
  const boundUserName = diagnostics.bound_user_full_name || "—"
  const boundUserEmail = diagnostics.bound_user_email || "—"
  const rows: Array<[string, string]> = [
    ["API URL", config.api_base_url],
    ["WEB URL", config.web_base_url],
    ["Интервал опроса (активный)", `${config.poll_active_secs} сек`],
    ["Максимальная пауза при ошибке", `${config.poll_error_max_secs} сек`],
    ["Лимит событий за запрос", String(config.poll_limit)],
    ["Последний опрос", diagnostics.last_poll_time ?? "еще не выполнялся"],
    ["Курсор", diagnostics.cursor === null ? "null" : String(diagnostics.cursor)],
    ["Статус токена", formatAuthStatus(diagnostics.auth_status)],
    ["Привязанный ФИО", boundUserName],
    ["Привязанный Email", boundUserEmail],
    ["Последняя ошибка", formatLastError(diagnostics.last_error)],
    ["Пауза уведомлений до", diagnostics.snoozed_until ?? "пауза выключена"],
    ["Кэш просмотренных событий (LRU)", String(diagnostics.seen_cache_size)],
  ]

  statusGrid.innerHTML = rows
    .map(([label, value]) => `<dt>${label}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("")
}

function renderActivityLog(entries: ActivityLogEntry[]): void {
  if (!entries.length) {
    activityLog.innerHTML = `<li><div class="log-message">Журнал пока пуст</div></li>`
    return
  }

  activityLog.innerHTML = entries
    .map(
      (entry) => `
        <li>
          <div class="log-meta">${escapeHtml(entry.at)} • ${escapeHtml(entry.level.toUpperCase())} • ${escapeHtml(entry.source)}</div>
          <div class="log-message">${escapeHtml(entry.message)}</div>
        </li>
      `,
    )
    .join("")
}

async function refreshDiagnostics(): Promise<void> {
  try {
    const [config, diagnostics, logEntries] = await Promise.all([
      invoke<AgentConfig>("get_agent_config"),
      invoke<DiagnosticsSnapshot>("get_diagnostics"),
      invoke<ActivityLogEntry[]>("get_activity_log"),
    ])
    latestDiagnostics = diagnostics
    renderStatus(config, diagnostics)
    renderActivityLog(logEntries)
    renderAuthActions(diagnostics)
  } catch (error) {
    setMessage(`Не удалось обновить диагностику: ${String(error)}`)
  }
}

async function startBinding(): Promise<void> {
  await invoke<string>("start_account_binding")
  setMessage("Открыт браузер для привязки аккаунта.")
}

async function clearToken(): Promise<void> {
  await invoke("clear_auth_token")
  setMessage("Вы вышли из аккаунта.")
}

async function clearLog(): Promise<void> {
  await invoke("clear_activity_log")
  setMessage("Журнал агента очищен.")
}

async function setSnooze(minutes: number): Promise<void> {
  await invoke("set_snooze_minutes", { minutes })
  setMessage(
    minutes === 0
      ? "Показ уведомлений возобновлен."
      : `Уведомления поставлены на паузу на ${minutes} мин.`,
  )
}

async function sendTestToast(): Promise<void> {
  await invoke("send_test_notification")
  setMessage("Тестовое уведомление отправлено.")
}

bindAccountButton.addEventListener("click", async () => {
  try {
    const authStatus = latestDiagnostics?.auth_status?.trim().toLowerCase()
    if (authStatus === "authenticated") {
      await clearToken()
    } else if (authStatus === "binding_pending") {
      setMessage("Привязка уже выполняется.")
    } else {
      await startBinding()
    }
    await refreshDiagnostics()
  } catch (error) {
    setMessage(`Не удалось выполнить действие авторизации: ${String(error)}`)
  }
})

clearTokenButton.addEventListener("click", async () => {
  try {
    await clearToken()
    await refreshDiagnostics()
  } catch (error) {
    setMessage(`Не удалось очистить токен: ${String(error)}`)
  }
})

snooze15Button.addEventListener("click", async () => {
  try {
    await setSnooze(15)
    await refreshDiagnostics()
  } catch (error) {
    setMessage(`Не удалось включить паузу: ${String(error)}`)
  }
})

snooze60Button.addEventListener("click", async () => {
  try {
    await setSnooze(60)
    await refreshDiagnostics()
  } catch (error) {
    setMessage(`Не удалось включить паузу: ${String(error)}`)
  }
})

resumeButton.addEventListener("click", async () => {
  try {
    await setSnooze(0)
    await refreshDiagnostics()
  } catch (error) {
    setMessage(`Не удалось возобновить уведомления: ${String(error)}`)
  }
})

openTrackerButton.addEventListener("click", async () => {
  try {
    await invoke("open_tracker_now")
  } catch (error) {
    setMessage(`Не удалось открыть EnbekTracker: ${String(error)}`)
  }
})

testToastButton.addEventListener("click", async () => {
  try {
    await sendTestToast()
    await refreshDiagnostics()
  } catch (error) {
    setMessage(`Не удалось отправить тестовое уведомление: ${String(error)}`)
  }
})

clearLogButton.addEventListener("click", async () => {
  try {
    await clearLog()
    await refreshDiagnostics()
  } catch (error) {
    setMessage(`Не удалось очистить журнал: ${String(error)}`)
  }
})

window.addEventListener("DOMContentLoaded", async () => {
  setMessage("Диагностика загружена.")
  await refreshDiagnostics()
  window.setInterval(() => {
    void refreshDiagnostics()
  }, 2000)
})
