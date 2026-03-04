# EnbekTracker Agent (Tauri)

Мини-приложение в трее для desktop-уведомлений Windows.

## Что делает агент

- работает как фоновый процесс в трее;
- привязывает аккаунт через браузер (без ручного ввода токена);
- хранит токен в защищенном хранилище ОС;
- опрашивает `GET /api/v1/desktop-events/poll` (HTTP polling);
- показывает системные уведомления Windows;
- по клику в уведомление открывает задачу в браузере;
- поддерживает паузу уведомлений (15/60 минут).

## Настройки (опционально)

- `TRACKER_AGENT_API_BASE_URL`
  - если не задан, агент автоопределяет:
    1) `ENBEK_AGENT_DEFAULT_API_BASE_URL` (вшитый в релиз при сборке),
    2) `ENBEK_AGENT_DEFAULT_API_BASE_URL_DIRECT` (или тот же URL),
    3) `http://localhost/api/v1`,
    4) затем `http://localhost:8888/api/v1`
- `TRACKER_AGENT_WEB_BASE_URL`
  - если не задан, агент автоопределяет:
    - `ENBEK_AGENT_DEFAULT_WEB_BASE_URL` (вшитый в релиз при сборке),
    - `http://localhost:5173` (когда API на `:8888` и dev frontend доступен),
    - иначе `http://localhost`
- `TRACKER_AGENT_POLL_LIMIT` (по умолчанию `100`)
- `TRACKER_AGENT_POLL_ACTIVE_SECS` (по умолчанию `5`)
- `TRACKER_AGENT_POLL_ERROR_MAX_SECS` (по умолчанию `60`)

## Запуск в dev

```bash
cd desktop-agent
npm install
npm run tauri:dev
```

## Сборка `.exe` на Windows (PowerShell)

```powershell
cd E:\DeV\Tracker\desktop-agent
npm install
npm run build
npm run tauri:build
```

Сборка с серверными URL по умолчанию (чтобы релизный агент не ходил на localhost):

```powershell
..\scripts\build-agent-win.ps1 `
  -Profile "server" `
  -ServerHost "tracker.example.com"
```

Примечание: если `-ServerHost` задан как IP/`localhost` без схемы, скрипт подставит `http://`.
Для доменного имени без схемы подставится `https://`.

Локальная сборка для теста:

```powershell
..\scripts\build-agent-win.ps1 -Profile "local"
```

Если нужно, можно явно передать URL:

```powershell
..\scripts\build-agent-win.ps1 `
  -Profile "server" `
  -WebBaseUrl "https://tracker.example.com" `
  -ApiBaseUrl "https://tracker.example.com/api/v1" `
  -ApiBaseUrlDirect "https://tracker.example.com/api/v1"
```

Артефакты после сборки:

- Installer `.exe`: `desktop-agent\src-tauri\target\release\bundle\nsis\*.exe`
- Portable `.exe` (binary): `desktop-agent\src-tauri\target\release\desktop-agent.exe`

Если нужен только инсталлятор `.exe`, используйте:

```powershell
npm run tauri:build:nsis
```

Альтернатива из корня проекта:

```powershell
.\scripts\build-agent-win.ps1 -NsisOnly
```

### Если видите `os error 5` (Access denied)

Это означает, что `desktop-agent.exe` занят запущенным процессом (обычно агент в трее).
Обновленный `build-agent-win.ps1` теперь сам останавливает агент перед сборкой.
Если ошибка осталась, закройте агент вручную через трей/Task Manager и повторите команду.

## Как подключить к вашему серверу

1. Запустите агент.
2. В трее нажмите `Привязать аккаунт`.
3. Откроется браузерная страница привязки. Если не авторизованы, выполните вход.
4. После подтверждения привязки проверьте в диагностике:
   - `Статус токена` = `Токен валиден`
   - `Последняя ошибка` = `нет`
5. Сверните окно, агент продолжит работу в трее.

Окно агента при нажатии на `X` скрывается в трей, а не завершает процесс.
