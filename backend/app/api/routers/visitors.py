"""방문자 토큰을 발급하는 라우터입니다.

브라우저가 처음 들어오면 Next BFF가 이 경로를 대신 불러 토큰을 받고, HttpOnly 쿠키에 저장합니다.
토큰이 응답 본문에 그대로 나오므로 브라우저는 이 경로를 직접 부를 수 없게 BFF에서 막아 둡니다.
"""

from fastapi import APIRouter, status

from app.api.responses import error_responses
from app.core.clock import Now
from app.core.db import DbSession
from app.schemas.accounts import VisitorCreated
from app.services import visitors as visitor_service

router = APIRouter(tags=["accounts"])


@router.post(
    "/visitors",
    summary="방문자 토큰 발급 (BFF 전용)",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401),
)
def create_visitor(db: DbSession, now: Now) -> VisitorCreated:
    """브라우저가 처음 들어오면 Next BFF가 대신 불러 방문자 토큰을 받습니다.

    토큰은 BFF가 HttpOnly 쿠키에 저장하고, 브라우저에는 본문을 그대로 주지 않습니다(BFF에서
    /api/visitors는 막혀 있음).
    토큰은 마지막 접속 후 7일 동안 유효하고, 쓸 때마다 만료가 늘어납니다.
    """
    return visitor_service.create_visitor(db, now)
