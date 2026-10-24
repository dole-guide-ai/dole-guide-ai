"""내 정보 창에서 사용자가 답한 내용을 보여 주고 한 줄씩 지우는 라우터입니다 (F-31).

따로 저장하는 테이블은 없고, 이력서와 지금 회차 신청서에서 사용자가 직접 답한 칸만 모아 보여
줍니다.
지운다는 것은 그 칸을 답변 필요 상태로 되돌리는 것입니다. 처리는 services/facts.py가 합니다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import CurrentAccount, get_current_account
from app.api.responses import error_responses
from app.core.clock import Now, Today
from app.core.db import DbSession
from app.schemas.common import UpdatesRead
from app.schemas.facts import FactList
from app.services import facts as fact_service

router = APIRouter(
    prefix="/accounts/{persona_id}", tags=["facts"], dependencies=[Depends(get_current_account)]
)


@router.get("/facts", summary="내 정보 (내가 답한 내용)", responses=error_responses(401, 404))
def list_facts(db: DbSession, account: CurrentAccount, today: Today) -> FactList:
    """작성한 서류(이력서 상태), 절차 상태(단계·다음 실업인정일), 내가 답한 내용(지금 회차 신청서의
    실업크레딧·통지 방법, 이력서에서 대화로 답한 칸)을 한 줄씩 모아 보여 주고, 서비스가 저장하지
    않는 정보 목록을 함께 돌려줍니다. 지울 수 있는 줄은 내가 답한 내용(group=facts)뿐입니다.
    """
    return fact_service.list_facts(db, account, today)


@router.delete(
    "/facts/{fact_id}",
    summary="내가 답한 내용 한 줄 지우기",
    responses=error_responses(401, 404, 409),
)
def delete_fact(fact_id: str, db: DbSession, account: CurrentAccount, now: Now) -> UpdatesRead:
    """그 칸을 답변 필요 상태로 되돌리고, 바뀐 칸을 돌려줍니다. 신청서 답은 지난 회차 답을 다시
    불러오지 않습니다.

    서류·절차 줄은 409 FACT_NOT_DELETABLE, 이미 제출한 신청서면 409 APPLICATION_LOCKED,
    없는 줄은 404입니다.
    """
    return fact_service.delete_fact(db, account, fact_id, now)
