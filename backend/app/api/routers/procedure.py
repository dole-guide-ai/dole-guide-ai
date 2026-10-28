"""수급 절차 상태를 조회하고 바꾸는 라우터입니다.

조회는 단계, 수급자 유형, 소정급여일수, 종료 예정일을 돌려줍니다.
변경(PATCH)은 교육 이수, 수급자격 신청일, 1차 인정일처럼 사용자가 고용센터에서 받은 사실만
입력하는 용도입니다.
"""

from fastapi import APIRouter

from app.api.deps import CurrentAccount
from app.api.responses import error_responses
from app.core.clock import Now, Today
from app.core.db import DbSession
from app.schemas.common import JsonPatch, UpdatesRead
from app.schemas.procedure import ProcedureRead
from app.services import accounts as account_service
from app.services import procedure as procedure_service

router = APIRouter(prefix="/accounts/{persona_id}", tags=["procedure"])


@router.get("/procedure", summary="절차 상태 조회", responses=error_responses(401, 404))
def get_procedure(db: DbSession, account: CurrentAccount, today: Today) -> ProcedureRead:
    """지금 절차 단계, 수급자 유형, 소정급여일수, 수급기간 끝과 종료 예정일을 돌려줍니다.

    종료 예정일은 급여 소진 예정일과 수급기간 끝(이직 다음 날부터 12개월) 중 이른 날이며, 실제는
    고용센터 확인이 필요합니다. 회차가 만들어졌으면 남은 회차 수와 마지막 회차 번호도 들어갑니다.
    """
    return account_service.read_procedure(db, account.user_id, today)


@router.patch(
    "/procedure",
    summary="절차 정보 입력 (센터에서 받은 사실)",
    responses=error_responses(401, 404, 409, 422),
)
def patch_procedure(
    db: DbSession, account: CurrentAccount, patch: JsonPatch, now: Now
) -> UpdatesRead:
    """교육 이수, 수급자격 신청일, 1차 실업인정일처럼 사용자가 고용센터에서 받은 사실을 입력합니다.

    JSON Patch로 `/education_done`, `/eligibility_applied_on`, `/first_recognition_date` 중 하나를
    보내며, 각각 한 번만 입력할 수 있습니다.
    1차 인정일이 들어오면 서버가 회차와 회차별 신청서를 한꺼번에 만듭니다. 회차 자체를 바꾸는 값은
    없습니다.
    순서는 교육 이수(`true`) → 수급자격 신청일(이직일 뒤·오늘까지) → 1차 인정일(신청일 + 7일
    이후)이고,
    순서가 틀리거나 이미 넣은 값이면 409 STAGE_ORDER, 날짜가 틀리면 422입니다. 한 번에 한 칸만
    보냅니다. 응답 entry는 바뀐 첫 화면입니다.
    """
    return procedure_service.patch_procedure(db, account, patch, now)
