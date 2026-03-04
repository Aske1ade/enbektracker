# Server Deployment Quickstart (IP/Domain, no localhost bindings)

This setup is intended for a plain Linux server where users open the app by:

- `http://<server-ip>`
- or `http://<your-domain>`

It uses:

- `docker-compose.server.yml` (separate server stack)
- `.env.deploy` (separate deployment env file)
- `scripts/deploy-server.sh` (one-command deploy)

## 1. Prepare env file

On the server, in project root:

```bash
cp .env.deploy.example .env.deploy
```

Edit `.env.deploy` and set at minimum:

- `SERVER_HOST`
- `SECRET_KEY`
- `FIRST_SUPERUSER`
- `FIRST_SUPERUSER_PASSWORD`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`

Optional (desktop-agent installer download from your server):

- `AGENT_DOWNLOADS_DIR` (host folder, default `./deploy/desktop-agent`)
- `DESKTOP_AGENT_BINARY_PATH` (path inside container, default `/opt/enbektracker/downloads/EnbekTracker_0.1.0_x64-setup.exe`)
- `DESKTOP_AGENT_DOWNLOAD_URL` (fallback redirect URL if local file is absent)

Prepare installer folder on server:

```bash
mkdir -p deploy/desktop-agent
```

Copy installer file into that folder (example):

```bash
cp /path/on/server/EnbekTracker_0.1.0_x64-setup.exe deploy/desktop-agent/
```

Then backend endpoint `GET /api/v1/utils/desktop-agent/download` will serve this file.

## 2. Deploy

```bash
./scripts/deploy-server.sh
```

Or directly:

```bash
docker compose --env-file .env.deploy -f docker-compose.server.yml up -d --build
```

## 3. Desktop agent (server and local build profiles)

Build installer for server URL defaults (Windows PowerShell):

```powershell
.\scripts\build-agent-win.ps1 -Profile "server" -ServerHost "your-server-domain-or-ip"
```

If `-ServerHost` is an IP/`localhost` without scheme, the script uses `http://`.
If it is a domain without scheme, the script uses `https://`.

Build installer for local test:

```powershell
.\scripts\build-agent-win.ps1 -Profile "local"
```

To publish installer via API endpoint `/api/v1/utils/desktop-agent/download`, copy the built `.exe` to `${AGENT_DOWNLOADS_DIR}` on server host and keep `DESKTOP_AGENT_BINARY_PATH` in `.env.deploy` pointing to `/opt/enbektracker/downloads/<file>.exe`.

## 3. Access

- Web UI: `http://SERVER_HOST` (port `APP_PORT`, default `80`)
- API docs: `http://SERVER_HOST/docs`

`frontend` proxies `/api`, `/docs`, `/redoc` internally to `backend`, so clients do not call `localhost`.

## 4. Update release

```bash
git pull
./scripts/deploy-server.sh
```

## 5. Useful commands

```bash
docker compose --env-file .env.deploy -f docker-compose.server.yml ps
docker compose --env-file .env.deploy -f docker-compose.server.yml logs -f backend
docker compose --env-file .env.deploy -f docker-compose.server.yml logs -f frontend
```
