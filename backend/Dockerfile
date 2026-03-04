FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

WORKDIR /app/

# Make dependency downloads resilient to slow/unstable network.
ENV POETRY_REQUESTS_TIMEOUT=180 \
    PIP_DEFAULT_TIMEOUT=180

# Install Poetry from distro packages to avoid TLS issues with external installer.
RUN set -e; \
    apt-get update; \
    apt-get install -y --no-install-recommends python3-poetry python3-poetry-plugin-export ca-certificates; \
    update-ca-certificates; \
    rm -rf /var/lib/apt/lists/*; \
    poetry config virtualenvs.create false; \
    poetry config installer.parallel false

# Install dependencies from pyproject.toml/poetry.lock and pip mirror settings.
COPY ./pyproject.toml ./poetry.lock /app/

# Allow installing dev dependencies to run tests
ARG INSTALL_DEV=false
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_TRUSTED_HOST=
RUN bash -c '\
set -e; \
if [ "$INSTALL_DEV" = "true" ]; then EXPORT_ARGS="--with dev"; else EXPORT_ARGS="--only main"; fi; \
PIP_ARGS=(--no-cache-dir --disable-pip-version-check --retries 10 --timeout 180 --index-url "$PIP_INDEX_URL"); \
if [ -n "$PIP_EXTRA_INDEX_URL" ]; then PIP_ARGS+=(--extra-index-url "$PIP_EXTRA_INDEX_URL"); fi; \
if [ -n "$PIP_TRUSTED_HOST" ]; then \
  for host in $(echo "$PIP_TRUSTED_HOST" | tr ",;" "  "); do \
    [ -n "$host" ] && PIP_ARGS+=(--trusted-host "$host"); \
  done; \
fi; \
for attempt in 1 2 3 4 5; do \
  poetry export --without-hashes --format requirements.txt $EXPORT_ARGS --output /tmp/requirements.txt && \
  python -m pip install "${PIP_ARGS[@]}" -r /tmp/requirements.txt && exit 0; \
  echo "pip install failed (attempt $attempt/5), retrying..."; \
  sleep $((attempt * 5)); \
done; \
echo "pip install failed after 5 attempts"; \
exit 1'

ENV PYTHONPATH=/app

COPY ./scripts/ /app/scripts/

COPY ./alembic.ini /app/

COPY ./prestart.sh /app/

COPY ./tests-start.sh /app/

COPY ./app /app/app
