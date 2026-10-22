"""고용24 불러오기를 흉내 낸 모의 목록을 돌려주는 라우터입니다.

경력증명(이력서용)과 입사지원 내역(구직활동용) 두 가지이며, 실제 고용24 연동은 하지 않고 seed 값을
씁니다.
목록에서 고른 항목을 실제로 넣는 일은 대화 턴에서 합니다. 아직 501 틀입니다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_account
from app.api.responses import error_responses
from app.core.errors import NotImplementedYetError
from app.schemas.imports import ImportList

router = APIRouter(
    prefix="/accounts/{persona_id}/imports",
    tags=["imports"],
    dependencies=[Depends(get_current_account)],
)


@router.get(
    "/career-certificates",
    summary="고용24 경력증명 불러오기 (모의)",
    responses=error_responses(401, 404, 501),
)
def list_career_certificates() -> ImportList:
    """고용24 이력보기를 흉내 낸 모의 경력·자격·훈련 목록을 돌려줍니다. 이미 이력서에 넣은 항목은
    is_recorded로 표시합니다.

    고른 항목을 실제로 넣는 일은 대화 메시지(import_ids)로 합니다. (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()


@router.get(
    "/job-applications",
    summary="고용24 입사지원 내역 불러오기 (모의)",
    responses=error_responses(401, 404, 501),
)
def list_job_applications() -> ImportList:
    """고용24 구직활동 불러오기를 흉내 낸 모의 입사지원 목록을 돌려줍니다. 이미 기록한 활동은
    is_recorded로 표시합니다.
    (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()
