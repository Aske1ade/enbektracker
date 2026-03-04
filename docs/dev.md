# Development DX

## Windows (PowerShell)

Use the PowerShell wrapper instead of `make`:

```powershell
.\scripts\dev.ps1 up
.\scripts\dev.ps1 status
.\scripts\dev.ps1 watch
.\scripts\dev.ps1 logs-backend
.\scripts\dev.ps1 logs-proxy
.\scripts\dev.ps1 logs-frontend
.\scripts\dev.ps1 doctor
.\scripts\dev.ps1 migrate
.\scripts\dev.ps1 sync-db-password
.\scripts\dev.ps1 repair-db
.\scripts\dev.ps1 reset-db
.\scripts\p0-verify.ps1
.\scripts\dev.ps1 test-backend
.\scripts\dev.ps1 test-frontend
.\scripts\dev.ps1 lint
.\scripts\dev.ps1 down
```

If script execution is blocked, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 up
```

## Start dev stack

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml up -d --build
```

## Start file sync/watch

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml watch
```

## Services

- Backend (auto-reload + prestart/migrations): `/start-reload.sh`
- Frontend dev (HMR): `npm run dev -- --host 0.0.0.0 --port 5173`

## Logs

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml logs -f backend
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml logs -f frontend-dev
```

## Checks

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml exec backend bash /app/scripts/lint.sh
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml exec backend bash /app/scripts/test.sh
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml exec frontend-dev npm run build
```

## Makefile shortcuts

`make` targets are convenient in Linux/WSL environments:

```bash
make dev-up
make dev-status
make dev-watch
make logs-backend
make logs-frontend
make dev-doctor
make dev-migrate
make dev-sync-db-password
make dev-repair-db
make dev-reset-db
make p0-verify
make test-backend
make test-frontend
make lint
```

## P0 stability verification

Run the deterministic 3-cycle verifier:

```powershell
.\scripts\p0-verify.ps1
```

Artifacts are saved in `logs/p0-<timestamp>/`:

- `p0-verify.log`
- `summary.json`
- `summary.md`
- `failure/cycle-*/` logs (if any cycle fails)

## Troubleshooting

### Quick bring-up (recommended order)

```powershell
.\scripts\dev.ps1 down
.\scripts\dev.ps1 up
.\scripts\dev.ps1 status
```

Expected status output:

1. `frontend (proxy)` -> `200`
2. `backend docs` -> `200`
3. `backend health` -> `200`
4. `backend login` -> `200`

If `backend login != 200`, run:

```powershell
.\scripts\dev.ps1 repair-db
.\scripts\dev.ps1 status
```

### DB reset/recovery strategy

1. Soft repair (keeps data):

```powershell
.\scripts\dev.ps1 repair-db
```

`repair-db` performs:
1. Postgres password sync
2. Alembic migrations
3. MinIO/init scripts
4. Superuser sync from `.env` (`FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`)

2. Hard reset (deletes data):

```powershell
.\scripts\dev.ps1 reset-db
```

3. Readiness check:

```powershell
.\scripts\dev.ps1 doctor
```

### Backend 500 on login: `password authentication failed for user "postgres"`

Reason:
- Postgres data volume was initialized with an old password, but `.env` now has a new `POSTGRES_PASSWORD`.

Fix (keep existing DB data):

```powershell
.\scripts\dev.ps1 sync-db-password
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml restart backend
```

Alternative (reset DB, data will be deleted):

```powershell
.\scripts\dev.ps1 reset-db
```

### Repeated `403` on `/api/v1/users/me`, `/api/v1/projects/`, `/api/v1/tasks/`

Reason:
- Frontend is calling protected endpoints without a valid token (expired/stale token or not logged in yet).

Fix:
- Re-login from UI.
- If needed, clear browser local storage for `http://localhost` and login again.

### Backend 500 on login: `relation "user" does not exist`

Reason:
- Backend was started with plain `uvicorn` in dev mode, so `prestart.sh` was skipped.
- Migrations and initial data were not applied.

Fix:

```powershell
.\scripts\dev.ps1 down
.\scripts\dev.ps1 up
.\scripts\dev.ps1 logs-backend
```

Expected backend startup sequence includes:
- `Running script /app/prestart.sh`
- `alembic upgrade ...`
- `Initial data created`
