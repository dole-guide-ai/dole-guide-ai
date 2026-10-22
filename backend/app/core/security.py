"""BFF 설정."""

import hashlib
import hmac
import secrets

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response
from app.schemas.common import ErrorCode

INTERNAL_SECRET_HEADER = "x-internal-secret"
# 공유 비밀 없이 열어 두는 경로. /health는 배포 헬스 체크가 씁니다.
PUBLIC_PATHS = frozenset({"/health"})
LOCAL_DOC_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"})


def new_visitor_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class InternalSecretMiddleware:
    """BFF에서 온 요청만 받습니다. `secret`이 비어 있으면(local) 확인하지 않습니다."""

    def __init__(self, app: ASGIApp, secret: str, allow_docs: bool = False) -> None:
        self.app = app
        self.secret = secret.encode("utf-8")
        self.open_paths = PUBLIC_PATHS | (LOCAL_DOC_PATHS if allow_docs else frozenset())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.secret or scope["path"] in self.open_paths:
            await self.app(scope, receive, send)
            return
        # CORS preflight는 헤더를 붙일 수 없으므로 통과시킵니다(실제 요청에서 막힘).
        if scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        sent = dict(scope["headers"]).get(INTERNAL_SECRET_HEADER.encode("latin-1"), b"")
        if not hmac.compare_digest(sent, self.secret):
            response = error_response(401, ErrorCode.INTERNAL_AUTH_FAILED)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
