"""
모든 실패 응답을 한 형식({code, message, details})으로 설정.
서비스는 HTTPException 대신 여기의 예외(NotFoundError, ConflictError 등)만 던지고, 전역 핸들러가
응답으로 바꿉니다.
같은 상태 코드 안에서 업무 오류를 구분할 때는 ConflictError(code=ErrorCode.ROUND_CLOSED)처럼
코드만 바꿔 던집니다.
"""

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
    413: ErrorCode.FILE_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_FILE,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    501: ErrorCode.NOT_IMPLEMENTED,
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
    ErrorCode.INTERNAL_AUTH_FAILED: "허용되지 않은 요청이에요.",
    ErrorCode.PERSONA_NOT_FOUND: "없는 시연 계정이에요.",
    ErrorCode.ACCOUNT_NOT_FOUND: "계정을 먼저 골라 주세요.",
    ErrorCode.STATUS_WITH_FIELDS: "저장·제출은 다른 칸과 따로 요청해 주세요.",
    ErrorCode.USER_ANSWER_ONLY: "이 칸은 대화로 직접 답해 주세요.",
    ErrorCode.VERSION_CONFLICT: "다른 곳에서 먼저 고쳤어요. 새로 불러온 뒤 다시 해 주세요.",
    ErrorCode.RESUME_NOT_READY: "꼭 필요한 칸을 모두 채우고 확인해야 저장할 수 있어요.",
    ErrorCode.STAGE_ORDER: "지금 단계에서는 할 수 없어요.",
    ErrorCode.NO_ACTIVE_ROUND: "아직 실업인정 회차가 없어요.",
    ErrorCode.ROUND_CLOSED: "지난 회차는 고칠 수 없어요.",
    ErrorCode.DUPLICATE_ACTIVITY: "이미 기록한 활동이에요.",
    ErrorCode.APPLICATION_LOCKED: "이 신청서는 지금 작성할 수 없어요. 안내를 확인해 주세요.",
    ErrorCode.CANNOT_SUBMIT: "아직 제출할 수 없어요. 남은 항목을 확인해 주세요.",
    ErrorCode.FACT_NOT_DELETABLE: "이 줄은 지울 수 없어요.",
    ErrorCode.TURN_IN_PROGRESS: "답을 만드는 중이에요. 끝난 뒤 다시 보내 주세요.",
    ErrorCode.IDEMPOTENCY_MISMATCH: "같은 요청 키로 다른 내용을 보냈어요.",
    ErrorCode.FILE_TOO_LARGE: "파일이 너무 커요. 4MB 이하로 올려 주세요.",
    ErrorCode.UNSUPPORTED_FILE: "올릴 수 없는 파일 형식이에요.",
    ErrorCode.EXTERNAL_UNAVAILABLE: "지금 목록을 불러올 수 없어요. 잠시 후 다시 시도해 주세요.",
    ErrorCode.NOT_IMPLEMENTED: "아직 준비 중인 기능이에요.",
    ErrorCode.TIMEOUT: "답이 너무 오래 걸려 멈췄어요. 다시 보내 주세요.",
}


class AppError(Exception):
    """서비스에서 던지는 기본 예외. 하위 클래스는 code·status만 바꿉니다.

    message는 사용자에게 그대로 보이는 한국어 문장입니다. 입력값·개인정보를 넣지 마세요.
    """

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status: int = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(
        self, message: str | None = None, details: Any = None, *, code: ErrorCode | None = None
    ) -> None:
        # 같은 상태 코드 안에서 업무 코드만 다를 때: ConflictError(code=ErrorCode.ROUND_CLOSED)
        if code is not None:
            self.code = code
        self.message = message or DEFAULT_MESSAGES[self.code]
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    code = ErrorCode.BAD_REQUEST
    status = HTTPStatus.BAD_REQUEST


class UnauthorizedError(AppError):
    code = ErrorCode.UNAUTHORIZED
    status = HTTPStatus.UNAUTHORIZED


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    status = HTTPStatus.NOT_FOUND


class ConflictError(AppError):
    code = ErrorCode.CONFLICT
    status = HTTPStatus.CONFLICT


class PayloadTooLargeError(AppError):
    code = ErrorCode.FILE_TOO_LARGE
    status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE


class UnsupportedMediaError(AppError):
    code = ErrorCode.UNSUPPORTED_FILE
    status = HTTPStatus.UNSUPPORTED_MEDIA_TYPE


class UnprocessableError(AppError):
    """Pydantic 검증은 통과했지만 업무 규칙상 받을 수 없는 값 (422)."""

    code = ErrorCode.VALIDATION_ERROR
    status = HTTPStatus.UNPROCESSABLE_ENTITY


class RateLimitedError(AppError):
    code = ErrorCode.RATE_LIMITED
    status = HTTPStatus.TOO_MANY_REQUESTS


class LlmUnavailableError(AppError):
    code = ErrorCode.LLM_UNAVAILABLE
    status = HTTPStatus.SERVICE_UNAVAILABLE


class ExternalUnavailableError(AppError):
    code = ErrorCode.EXTERNAL_UNAVAILABLE
    status = HTTPStatus.SERVICE_UNAVAILABLE


class NotImplementedYetError(AppError):
    """라우터 틀만 있고 아직 구현하지 않은 엔드포인트 (501). 기능 PR에서 지웁니다."""

    code = ErrorCode.NOT_IMPLEMENTED
    status = HTTPStatus.NOT_IMPLEMENTED


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
