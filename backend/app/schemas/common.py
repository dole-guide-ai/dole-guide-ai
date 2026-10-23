"""여러 API가 같이 쓰는 응답·요청 스키마입니다.

실패 응답 형식과 오류 코드 목록, 목록 응답(Page),
서류 칸 하나의 값과 상태(FormField), 부분 수정 요청(JSON Patch), 바뀐 칸을 알리는
형식(FormUpdate)이 있습니다.
새 오류 코드는 이 파일의 ErrorCode에만 추가합니다.
"""

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel
from pydantic import Field as PydanticField


class ErrorCode(StrEnum):
    """프론트와 공유하는 오류 코드. 새 코드는 여기에만 추가합니다(대문자 스네이크)."""

    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # 인증·계정 (설계 3.1)
    INTERNAL_AUTH_FAILED = "INTERNAL_AUTH_FAILED"
    PERSONA_NOT_FOUND = "PERSONA_NOT_FOUND"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    # 입력 (422)
    STATUS_WITH_FIELDS = "STATUS_WITH_FIELDS"
    USER_ANSWER_ONLY = "USER_ANSWER_ONLY"
    # 상태 충돌 (409)
    VERSION_CONFLICT = "VERSION_CONFLICT"
    RESUME_NOT_READY = "RESUME_NOT_READY"
    STAGE_ORDER = "STAGE_ORDER"
    ROUND_CLOSED = "ROUND_CLOSED"
    DUPLICATE_ACTIVITY = "DUPLICATE_ACTIVITY"
    APPLICATION_LOCKED = "APPLICATION_LOCKED"
    CANNOT_SUBMIT = "CANNOT_SUBMIT"
    FACT_NOT_DELETABLE = "FACT_NOT_DELETABLE"
    TURN_IN_PROGRESS = "TURN_IN_PROGRESS"
    IDEMPOTENCY_MISMATCH = "IDEMPOTENCY_MISMATCH"
    # 리소스 없음 (404)
    NO_ACTIVE_ROUND = "NO_ACTIVE_ROUND"
    # 파일
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    # 외부·미구현
    EXTERNAL_UNAVAILABLE = "EXTERNAL_UNAVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    # 대화 턴 도중 시간 초과 (SSE error 이벤트에만)
    TIMEOUT = "TIMEOUT"


class FieldError(BaseModel):
    field: str
    type: str


class ErrorResponse(BaseModel):
    """모든 실패 응답의 형식."""

    code: ErrorCode
    message: str
    details: Any = None


class Page[T](BaseModel):
    """목록 응답. 성공 응답은 감싸지 않고, 목록만 이 형식을 씁니다."""

    items: list[T]
    total: int


# ── 서류 칸 · 변경 알림 (설계 3.11) ─────────────────────────────


class FieldStatus(StrEnum):
    """칸 상태 6종 (설계 8절 CHECK)."""

    MISSING = "missing"
    EXTRACTED = "extracted"
    CONFIRMED = "confirmed"
    CONFLICT = "conflict"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


class FieldSource(StrEnum):
    USER_ANSWER = "user_answer"
    DOC = "doc"
    IMPORT = "import"
    AUTO = "auto"
    DIRECT = "direct"
    SEED = "seed"
    ACCOUNT = "account"


class FormField(BaseModel):
    """서류 칸 하나. 이력서·신청서 jsonb 안에서 값과 상태를 같이 둡니다 (설계 3.11 `Field`)."""

    value: Any = None
    status: FieldStatus = FieldStatus.MISSING
    source: FieldSource | None = None
    transformed: bool = False
    evidence: dict[str, Any] | None = None
    answered_on: date | None = None


class PatchOpName(StrEnum):
    ADD = "add"
    REPLACE = "replace"
    REMOVE = "remove"


class PatchErrorType(StrEnum):
    """칸 고치기 422의 details.type (CONVENTIONS 7절 `[{field, type}]`, 입력값 대신 이유만)."""

    UNKNOWN_PATH = "unknown_path"
    REQUIRED = "required"
    DATE_FORMAT = "date_format"
    NUMBER = "number"
    TEXT = "text"
    OUT_OF_ROUND = "out_of_round"
    BAD_SHAPE = "bad_shape"
    TOO_MANY = "too_many"


class JsonPatchOp(BaseModel):
    """JSON Patch 한 줄. `path`는 `/careers/{item_id}/company_name`처럼 칸을 가리킵니다."""

    op: Literal["add", "replace", "remove"]
    path: str = PydanticField(pattern=r"^/")
    value: Any = None


type JsonPatch = list[JsonPatchOp]


class FormName(StrEnum):
    RESUME = "resume"
    ACTIVITIES = "activities"
    APPLICATION = "application"
    PROCEDURE = "procedure"


class FormUpdate(BaseModel):
    """바뀐 칸 하나. 대화 턴의 `form_update` 이벤트와 REST 쓰기 응답이 같은 형태입니다."""

    form: FormName
    path: str
    op: Literal["add", "replace", "remove"]
    value: Any = None
    status: FieldStatus | None = None
    source: FieldSource | None = None
    transformed: bool = False
    evidence: dict[str, Any] | None = None
    completeness: dict[str, int] | None = None


class UpdatesRead(BaseModel):
    """쓰기 응답 `{updates}`. 진입 결과가 바뀌면 `entry`도 담습니다(타입은 accounts.Entry)."""

    updates: list[FormUpdate]
    entry: dict[str, Any] | None = None
