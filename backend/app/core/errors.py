"""공통 에러 형식. 모든 실패 응답은 `ErrorResponse {code, message, details}`"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorCode, ErrorResponse, FieldError

logger = logging.getLogger(__name__)


# HTTPException(상태 코드만 있는 오류)을 코드로 바꿀 때 씁니다.
STATUS_TO_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.BAD_REQUEST,
    409: ErrorCode.CONFLICT,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
}

DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.BAD_REQUEST: "요청을 처리할 수 없어요.",
    ErrorCode.VALIDATION_ERROR: "입력한 내용을 다시 확인해 주세요.",
    ErrorCode.UNAUTHORIZED: "다시 접속해 주세요.",
    ErrorCode.FORBIDDEN: "이 작업을 할 수 없어요.",
    ErrorCode.NOT_FOUND: "찾는 정보가 없어요.",
    ErrorCode.CONFLICT: "이미 처리된 요청이에요.",
    ErrorCode.RATE_LIMITED: "요청이 많아요. 잠시 후 다시 시도해 주세요.",
    ErrorCode.LLM_UNAVAILABLE: "AI 도우미가 잠시 응답하지 않아요. 잠시 후 다시 시도해 주세요.",
    ErrorCode.INTERNAL_ERROR: "일시적인 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
}


class AppError(Exception):
    """서비스에서 던지는 기본 예외. 하위 클래스는 code·status만 바꿉니다.

    message는 사용자에게 그대로 보이는 한국어 문장입니다. 입력값·개인정보를 넣지 마세요.
    """

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status: int = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str | None = None, details: Any = None) -> None:
        self.message = message or DEFAULT_MESSAGES[self.code]
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    code = ErrorCode.BAD_REQUEST
    status = HTTPStatus.BAD_REQUEST


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    status = HTTPStatus.NOT_FOUND


class ConflictError(AppError):
    code = ErrorCode.CONFLICT
    status = HTTPStatus.CONFLICT


class RateLimitedError(AppError):
    code = ErrorCode.RATE_LIMITED
    status = HTTPStatus.TOO_MANY_REQUESTS


class LlmUnavailableError(AppError):
    code = ErrorCode.LLM_UNAVAILABLE
    status = HTTPStatus.SERVICE_UNAVAILABLE


def error_response(
    status: int, code: ErrorCode, message: str | None = None, details: Any = None
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message or DEFAULT_MESSAGES[code], details=details)
    return JSONResponse(status_code=status, content=jsonable_encoder(body))


def _field_errors(exc: RequestValidationError) -> list[FieldError]:
    # 입력값(input)은 개인정보일 수 있어 응답에 넣지 않고 위치·종류만 돌려줍니다.
    return [
        FieldError(
            field=".".join(str(part) for part in err["loc"] if part != "body"),
            type=err["type"],
        )
        for err in exc.errors()
    ]


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    logger.info("app error code=%s path=%s", exc.code, request.url.path)
    return error_response(exc.status, exc.code, exc.message, exc.details)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return error_response(
        HTTPStatus.UNPROCESSABLE_ENTITY, ErrorCode.VALIDATION_ERROR, details=_field_errors(exc)
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return error_response(exc.status_code, code)


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # 내부 내용은 응답에 숨기고, 로그에는 예외 종류·경로만 남깁니다(요청 본문 금지).
    logger.error(
        "unexpected error type=%s path=%s", type(exc).__name__, request.url.path, exc_info=exc
    )
    return error_response(HTTPStatus.INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
