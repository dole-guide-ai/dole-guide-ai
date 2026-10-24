"""고용24 불러오기를 흉내 낸 모의 목록을 돌려주는 라우터입니다.

경력증명(이력서용)과 입사지원 내역(구직활동용) 두 가지이며, 실제 고용24 연동은 하지 않고 입장할 때
seed에서 복사한 목록을 씁니다. 고른 항목 넣기는 화면(POST /apply)과 대화 턴(import_ids)이 같은
서비스를 씁니다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import CurrentAccount, get_current_account
from app.api.responses import error_responses
from app.core.clock import Today
from app.core.db import DbSession
from app.schemas.common import UpdatesRead
from app.schemas.imports import ImportApply, ImportList
from app.services import imports as import_service

router = APIRouter(
    prefix="/accounts/{persona_id}/imports",
    tags=["imports"],
    dependencies=[Depends(get_current_account)],
)


@router.get(
    "/career-certificates",
    summary="고용24 경력증명 불러오기 (모의)",
    responses=error_responses(401, 404),
)
def list_career_certificates(db: DbSession, account: CurrentAccount) -> ImportList:
    """고용24 이력보기를 흉내 낸 모의 경력·자격·훈련 목록을 돌려줍니다. 이미 이력서에 넣은 항목은
    is_recorded로 표시합니다.

    항목 값(values)은 category·title·detail입니다.
    고른 항목을 실제로 넣는 일은 대화 메시지(import_ids)로 합니다.
    """
    return import_service.list_career_certificates(db, account)


@router.get(
    "/job-applications",
    summary="고용24 입사지원 내역 불러오기 (모의)",
    responses=error_responses(401, 404),
)
def list_job_applications(db: DbSession, account: CurrentAccount) -> ImportList:
    """고용24 구직활동 불러오기를 흉내 낸 모의 입사지원 목록을 돌려줍니다. 이미 기록한 활동은
    is_recorded로 표시합니다.

    항목 값(values)은 category·title·detail·date(지원일)입니다.
    """
    return import_service.list_job_applications(db, account)


@router.post(
    "/apply",
    summary="고른 불러오기 항목 넣기 (모의)",
    responses=error_responses(401, 404, 409, 422),
)
def apply_imports(
    db: DbSession, account: CurrentAccount, today: Today, body: ImportApply
) -> UpdatesRead:
    """고른 항목을 넣습니다 (F-10). 입사지원은 구직활동(출처 import, 고용24 경로)으로, 경력·자격은
    이력서 칸(출처 import)으로 들어가고, 목록에서는 이미 넣음(is_recorded)이 됩니다.

    목록에 없는 항목은 404, 이미 넣은 항목은 409, 지난 회차 입사지원은 409 ROUND_CLOSED, 직업훈련
    이력은 아직 대화로만 받아 422입니다. 응답 updates는 바뀐 활동·이력서 칸과 회차 점검입니다.
    """
    return import_service.apply_imports(db, account, body.import_ids, today)
