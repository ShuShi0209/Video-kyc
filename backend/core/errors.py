"""API error handling.

Every error leaves the API in the shape API_CONTRACT.md defines::

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("video_kyc.errors")

_STATUS_TO_CODE = {
    400: "INVALID_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "INVALID_REQUEST",
    409: "INVALID_STATE",
    422: "VALIDATION_ERROR",
}

_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_body(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _validation_fields(exc: RequestValidationError) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ())]
        if loc and loc[0] in _LOCATION_PREFIXES:
            loc = loc[1:]
        fields.setdefault(".".join(loc) or "request", str(err.get("msg", "Invalid value")))
    return fields


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException):
        code = _STATUS_TO_CODE.get(exc.status_code, "INTERNAL_ERROR" if exc.status_code >= 500 else "INVALID_REQUEST")
        if exc.status_code == 404:
            message = "The requested resource was not found."
        else:
            message = exc.detail if isinstance(exc.detail, str) else "The request could not be processed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "The request contains invalid fields.", {"fields": _validation_fields(exc)}),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception):
        logger.exception("Unhandled error while processing request")
        return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "An unexpected error occurred."))
