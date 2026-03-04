#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.server.yml"
ENV_FILE="${1:-${ROOT_DIR}/.env.deploy}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ENV file not found: ${ENV_FILE}"
  echo "Copy ${ROOT_DIR}/.env.deploy.example to ${ROOT_DIR}/.env.deploy and fill required values."
  exit 1
fi

if grep -E -q 'your-server-ip-or-domain|replace-with-' "${ENV_FILE}"; then
  echo "ENV file still contains placeholder values."
  echo "Please edit ${ENV_FILE} before deployment."
  exit 1
fi

echo "Validating compose config..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config >/dev/null

echo "Starting services..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build

echo "Deployment complete. Current status:"
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
