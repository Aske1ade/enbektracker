import logging
import threading
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api.main import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.jobs.deadline_notifications import send_deadline_notifications
from app.schemas.common import APIErrorResponse, ValidationIssue


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

configure_logging()
logger = logging.getLogger("app.request")
REQUEST_ID_HEADER = "X-Request-ID"


def _deadline_sync_interval_seconds() -> int:
    return max(120, min(settings.TASK_DEADLINE_RECALC_INTERVAL_SECS, 300))


def _run_background_jobs(stop_event: threading.Event) -> None:
    interval = _deadline_sync_interval_seconds()
    logger.info("Tracker background jobs started (interval=%ss)", interval)
    while not stop_event.is_set():
        try:
            send_deadline_notifications()
        except Exception as exc:  # pragma: no cover - guarded runtime path
            logger.exception("Tracker background jobs failure", exc_info=exc)
        if stop_event.wait(interval):
            break


@asynccontextmanager
async def lifespan(_app: FastAPI):
    worker_stop: threading.Event | None = None
    worker: threading.Thread | None = None
    if settings.TRACKER_BACKGROUND_JOBS_ENABLED:
        worker_stop = threading.Event()
        worker = threading.Thread(
            target=_run_background_jobs,
            args=(worker_stop,),
            name="tracker-background-jobs",
            daemon=True,
        )
        worker.start()
    try:
        yield
    finally:
        if worker_stop is not None:
            worker_stop.set()
        if worker is not None:
            worker.join(timeout=5)


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id
    return str(uuid4())


@app.middleware("http")
async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid4()))
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    duration_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "%s %s -> %s (%.2fms) request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = get_request_id(request)
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    payload = APIErrorResponse(
        code=f"http_{exc.status_code}",
        detail=detail,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(exclude_none=True),
        headers={REQUEST_ID_HEADER: request_id},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = get_request_id(request)
    issues = [
        ValidationIssue(
            loc=list(issue.get("loc", [])),
            msg=str(issue.get("msg", "")),
            type=str(issue.get("type", "")),
        )
        for issue in exc.errors()
    ]
    payload = APIErrorResponse(
        code="validation_error",
        detail="Request validation failed",
        request_id=request_id,
        issues=issues,
    )
    return JSONResponse(
        status_code=422,
        content=payload.model_dump(exclude_none=True),
        headers={REQUEST_ID_HEADER: request_id},
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    logger.exception("Unhandled error request_id=%s", request_id, exc_info=exc)
    payload = APIErrorResponse(
        code="internal_error",
        detail="Internal server error",
        request_id=request_id,
    )
    return JSONResponse(
        status_code=500,
        content=payload.model_dump(exclude_none=True),
        headers={REQUEST_ID_HEADER: request_id},
    )


app.include_router(api_router, prefix=settings.API_V1_STR)
