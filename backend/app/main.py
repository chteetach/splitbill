import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.errors import AppError, error_body
from app.routers import expenses, groups, users

logger = logging.getLogger(__name__)


def _field_name(loc: tuple) -> str:
    # ("body", "split", "exact", "shares", "bob") -> "split.shares.bob"
    parts = [str(p) for p in loc if p not in ("body", "equal", "exact")]
    return ".".join(parts) or "request"


def _clean_message(msg: str) -> str:
    return msg.removeprefix("Value error, ")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": _field_name(tuple(e["loc"])), "message": _clean_message(e["msg"])}
            for e in exc.errors()
        ]
        first = details[0] if details else {"field": "request", "message": "Invalid request"}
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error", f"{first['field']}: {first['message']}", details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=error_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500, content=error_body("internal_error", "Something went wrong")
        )


def create_app() -> FastAPI:
    app = FastAPI(title="SplitBill API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Idempotent-Replayed"],
    )
    register_error_handlers(app)
    app.include_router(users.router)
    app.include_router(groups.router)
    app.include_router(expenses.router)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
