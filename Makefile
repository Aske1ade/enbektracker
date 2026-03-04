COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml
POWERSHELL = powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1

.PHONY: dev-up dev-down dev-status dev-watch logs-backend logs-frontend test-backend test-frontend lint dev-doctor dev-migrate dev-sync-db-password dev-repair-db dev-reset-db p0-verify

dev-up:
	$(COMPOSE_DEV) up -d --build

dev-down:
	$(COMPOSE_DEV) down

dev-status:
	$(POWERSHELL) status

dev-watch:
	$(COMPOSE_DEV) watch

logs-backend:
	$(COMPOSE_DEV) logs -f backend

logs-frontend:
	$(COMPOSE_DEV) logs -f frontend-dev

test-backend:
	$(COMPOSE_DEV) exec backend bash /app/scripts/test.sh

test-frontend:
	$(COMPOSE_DEV) exec frontend-dev npm run build

lint:
	$(COMPOSE_DEV) exec backend bash /app/scripts/lint.sh
	$(COMPOSE_DEV) exec frontend-dev npm run lint

dev-doctor:
	$(POWERSHELL) doctor

dev-migrate:
	$(POWERSHELL) migrate

dev-sync-db-password:
	$(POWERSHELL) sync-db-password

dev-repair-db:
	$(POWERSHELL) repair-db

dev-reset-db:
	$(POWERSHELL) reset-db

p0-verify:
	powershell -ExecutionPolicy Bypass -File .\scripts\p0-verify.ps1
