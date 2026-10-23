"""구직활동 기록을 조회·추가·수정·삭제하는 라우터입니다.

활동은 날짜만 저장하고, 어느 회차에 속하는지는 회차 대상기간으로 계산합니다. 지난 회차 활동은 고칠
수 없습니다.
추천을 예정 활동으로 넣기(F-19)와 칸 고치기(F-12)만 동작하고, 나머지는 아직 501 틀입니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentAccount, IdempotencyKey, get_current_account
from app.api.responses import error_responses
from app.core.clock import Today
from app.core.db import DbSession
from app.core.errors import NotImplementedYetError
from app.schemas.activities import ActivityCreate, ActivityRead
from app.schemas.common import JsonPatch, Page, UpdatesRead
from app.services import activities as activity_service
from app.services import recommendations as recommendation_service

router = APIRouter(
    prefix="/accounts/{persona_id}",
    tags=["activities"],
    dependencies=[Depends(get_current_account)],
)


@router.get("/activities", summary="구직활동 목록", responses=error_responses(401, 404, 501))
def list_activities(round: Annotated[int | None, Query(ge=1)] = None) -> Page[ActivityRead]:
    """이 계정의 활동 기록을 돌려줍니다. round를 주면 그 회차 대상기간의 활동만 돌려줍니다.

    활동의 회차 번호는 저장된 값이 아니라 대상기간으로 계산한 값입니다. (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()


@router.post(
    "/activities",
    summary="구직활동 추가",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404, 409, 422, 501),
)
def create_activity(
    body: ActivityCreate,
    db: DbSession,
    account: CurrentAccount,
    today: Today,
    idempotency_key: IdempotencyKey = None,
) -> UpdatesRead:
    """활동을 직접 기록하거나, 추천을 예정 활동으로 넣습니다.

    - 추천 넣기(F-19): recommendation_id만 보냅니다. 인정일 전날(오늘이 인정일이면 오늘) 예정으로
      들어가고 계산에는 넣지 않습니다. 지금 추천 목록에 없으면 409 CONFLICT, 같은 추천을 이미
      넣었으면 409 DUPLICATE_ACTIVITY, 오늘이 속한 회차가 없으면 404 NO_ACTIVE_ROUND입니다.
    - 직접 기록: 날짜·종류·경로·회사 등 활동 값을 보냅니다. (활동 기록 기능에서 붙일 예정이라 501)

    Idempotency-Key 헤더를 주면 같은 요청이 두 번 와도 한 번만 만듭니다.
    """
    return recommendation_service.create_activity(db, account, body, idempotency_key, today)


@router.patch(
    "/activities/{activity_id}",
    summary="구직활동 고치기",
    responses=error_responses(401, 404, 409, 422),
)
def patch_activity(
    activity_id: str, patch: JsonPatch, db: DbSession, account: CurrentAccount, today: Today
) -> UpdatesRead:
    """패널에서 활동 칸을 직접 고칩니다 (F-12). 예: `[{"op": "replace", "path": "/org_name",
    "value": "OO물산"}]`

    - 고칠 수 있는 칸: activity_date, kind, route, org_name, job_title, search_method,
      apply_method, contact_dept, result, hours. 그 밖의 칸·틀린 형식은 422(날짜는 YYYY-MM-DD,
      새 날짜도 이번 회차 대상기간 안). activity_date·kind는 지울 수 없습니다.
    - 지난 회차 활동은 409 ROUND_CLOSED, 없는 활동은 404입니다.
    - 고친 활동은 출처가 직접 입력(direct)이 됩니다. 응답 updates는 고친 활동 하나입니다.
    """
    return activity_service.patch_activity(db, account, activity_id, patch, today)


@router.delete(
    "/activities/{activity_id}",
    summary="구직활동 빼기",
    responses=error_responses(401, 404, 409, 501),
)
def delete_activity(activity_id: str) -> UpdatesRead:
    """활동을 지우고 다시 계산한 회차 점검 결과를 바뀐 칸(updates)으로 돌려줍니다.

    지난 회차 활동은 409 ROUND_CLOSED입니다. (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()
