"""라우터들이 공통으로 쓰는 의존성(Depends) 모음입니다.

요청의 Bearer 토큰으로 방문자를 찾고, 경로의 persona_id로 그 방문자가 입장한 계정을 찾아 라우터에
넘겨 줍니다.
여기서는 이미 있는 방문자와 계정을 찾아 확인만 하고, 새로 만들지는 않습니다(생성은
services/visitors.py·accounts.py).
토큰이 없거나 만료면 401, 없는 시연 계정이거나 아직 입장하지 않은 계정이면 404로 끝납니다.
서류 수정의 If-Match 헤더, POST 재시도 방지용 Idempotency-Key 헤더도 여기서 꺼냅니다.
"""

from typing import Annotated

from fastapi import Depends, Header, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.clock import Now
from app.core.db import DbSession
from app.core.errors import ConflictError
from app.schemas.common import ErrorCode
from app.services import accounts as account_service
from app.services import visitors as visitor_service

_bearer = HTTPBearer(auto_error=False, description="BFF가 쿠키의 방문자 토큰을 넣습니다.")


def get_current_visitor(
    db: DbSession,
    now: Now,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> visitor_service.VisitorContext:
    token = credentials.credentials if credentials else None
    return visitor_service.authenticate(db, token, now)


CurrentVisitor = Annotated[visitor_service.VisitorContext, Depends(get_current_visitor)]

PersonaId = Annotated[str, Path(pattern=r"^[a-z0-9_-]{1,32}$", description="시연 계정 ID")]


def get_current_account(
    db: DbSession, visitor: CurrentVisitor, persona_id: PersonaId
) -> account_service.AccountContext:
    return account_service.find_account(db, visitor.visitor_id, persona_id)


CurrentAccount = Annotated[account_service.AccountContext, Depends(get_current_account)]

IDEMPOTENCY_KEY_MAX_LENGTH = 100

IF_MATCH_MISSING_MESSAGE = "서류를 다시 불러온 뒤 고쳐 주세요."


def require_if_match(
    if_match: Annotated[
        str | None,
        Header(
            alias="If-Match",
            description="서류 GET 응답의 ETag (필수). 없거나 다르면 409 VERSION_CONFLICT",
        ),
    ] = None,
) -> str:
    """서류 PATCH는 If-Match가 꼭 있어야 합니다 (설계 3.11 낙관적 잠금).

    헤더가 없으면 어느 버전을 고치는지 몰라 다른 탭의 변경을 덮어쓸 수 있어 409로 막습니다.
    대화 턴의 AI 도구는 라우터를 거치지 않고 서비스를 바로 부르므로 이 검사를 받지 않습니다.
    """
    if if_match is None:
        raise ConflictError(code=ErrorCode.VERSION_CONFLICT, message=IF_MATCH_MISSING_MESSAGE)
    return if_match


IfMatch = Annotated[str, Depends(require_if_match)]
IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        max_length=IDEMPOTENCY_KEY_MAX_LENGTH,
        description="POST 재시도 중복 방지 키",
    ),
]
