"""내 정보 창에서 사용자가 답한 내용을 보여 주고 한 줄씩 지우는 라우터입니다.

따로 저장하는 테이블은 없고, 이력서와 지금 회차 신청서에서 사용자가 직접 답한 칸만 모아 보여
줍니다.
지운다는 것은 그 칸을 답변 필요 상태로 되돌리는 것입니다. 아직 501 틀입니다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_account
from app.api.responses import error_responses
from app.core.errors import NotImplementedYetError
from app.schemas.common import UpdatesRead
from app.schemas.facts import FactList

router = APIRouter(
    prefix="/accounts/{persona_id}", tags=["facts"], dependencies=[Depends(get_current_account)]
)


@router.get("/facts", summary="내 정보 (내가 답한 내용)", responses=error_responses(401, 404, 501))
def list_facts() -> FactList:
    """이력서와 지금 회차 신청서에서 사용자가 직접 답한 칸을 한 줄씩 모아 보여 주고, 서비스가
    저장하지 않는 정보 목록을 함께 돌려줍니다.
    (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()


@router.delete(
    "/facts/{fact_id}",
    summary="내가 답한 내용 한 줄 지우기",
    responses=error_responses(401, 404, 409, 501),
)
def delete_fact(fact_id: str) -> UpdatesRead:
    """그 칸을 답변 필요 상태로 되돌리고, 바뀐 칸을 돌려줍니다.

    지난 회차 신청서의 답처럼 지울 수 없는 줄이면 409 FACT_NOT_DELETABLE입니다. (아직 구현 전이라
    501)
    """
    raise NotImplementedYetError()
