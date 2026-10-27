"""시연 계정 카드 목록과 계정 입장·조회·삭제를 다루는 라우터입니다.

카드 목록은 로그인 화면이, 입장(PUT)은 카드를 눌렀을 때, 조회(GET)는 새로고침 때, 삭제(DELETE)는
처음부터 다시를 누를 때 씁니다.
입장은 같은 요청을 여러 번 보내도 결과가 같습니다. 처음이면 201로 만들고, 이미 있으면 200으로
이어서 돌려줍니다.
실제 처리는 services/accounts.py가 하고, 이 파일은 HTTP 상태 코드와 헤더만 다룹니다.
"""

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentAccount, CurrentVisitor, PersonaId
from app.api.responses import error_responses
from app.core.clock import Now
from app.core.db import DbSession
from app.schemas.accounts import AccountRead, PersonaList
from app.services import accounts as account_service

router = APIRouter(tags=["accounts"])


@router.get("/personas", summary="시연 계정 카드 목록", responses=error_responses(401))
def list_personas(db: DbSession, visitor: CurrentVisitor) -> PersonaList:
    """로그인 화면에 보일 시연 계정 카드 3개(박진수·최영수·이정호)를 돌려줍니다.

    카드에는 이름·나이·직종·한마디·상태 요약이 들어 있고, 이 방문자가 이미 입장한 계정이면 진행
    요약(예: 실업인정 중)이 붙습니다.
    방문자 토큰(Authorization: Bearer)이 필요합니다.
    """
    return account_service.list_persona_cards(db, visitor.visitor_id)


@router.put(
    "/accounts/{persona_id}",
    summary="계정 입장 (처음이면 만들고, 있으면 이어서)",
    responses={201: {"model": AccountRead}, **error_responses(401, 404)},
)
def enter_account(
    db: DbSession, visitor: CurrentVisitor, persona_id: PersonaId, now: Now, response: Response
) -> AccountRead:
    """카드를 눌렀을 때 부릅니다. 같은 요청을 여러 번 보내도 결과가 같습니다.

    - 이 방문자가 처음 고른 계정이면 seed를 오늘 날짜 기준으로 바꿔 계정을 만들고 201과 Location
      헤더를 돌려줍니다.
    - 이미 있는 계정이면 하던 데서 이어서 200을 돌려줍니다.

    응답에는 절차 상태, 오늘이 속한 회차, 첫 화면을 그리는 진입 결과(entry)가 들어 있습니다.
    """
    account, created = account_service.enter(db, visitor.visitor_id, persona_id, now)
    if created:
        response.status_code = status.HTTP_201_CREATED
        response.headers["Location"] = f"/accounts/{persona_id}"
    return account


@router.get(
    "/accounts/{persona_id}", summary="계정 상태 다시 불러오기", responses=error_responses(401, 404)
)
def get_account(db: DbSession, account: CurrentAccount, now: Now) -> AccountRead:
    """새로고침했을 때 부릅니다. 계정 상태를 오늘 날짜로 다시 진단해, 지금 회차와 진입 결과를 새로
    계산해 돌려줍니다.

    아직 입장하지 않은 계정이면 404 ACCOUNT_NOT_FOUND입니다.
    """
    return account_service.read_account(db, account, now, greet=True)


@router.delete(
    "/accounts/{persona_id}",
    summary="처음부터 다시 (계정 삭제)",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404, 409),
)
def delete_account(db: DbSession, account: CurrentAccount) -> Response:
    """이 방문자의 이 계정만 지웁니다. 서류·회차·활동·대화와 업로드 파일이 함께 지워집니다.

    다른 시연 계정은 그대로입니다. 이어서 PUT으로 다시 입장하면 seed 상태로 처음부터 시작합니다.
    """
    account_service.delete_account(db, account)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
