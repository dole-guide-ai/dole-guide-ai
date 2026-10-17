"""요청마다 `X-Request-ID`를 붙여 화면의 오류와 서버 로그를 연결합니다."""

import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Request-ID"
# 클라이언트가 보낸 값은 형식이 맞을 때만 이어받습니다(로그 주입 방지).
VALID_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(HEADER.lower().encode(), b"").decode()
        request_id = incoming if VALID_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((HEADER.encode(), request_id.encode()))
            await send(message)

        await self.app(scope, receive, send_with_id)
