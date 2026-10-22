"""실업인정 회차와 회차별 신청서를 다루는 라우터입니다.

회차는 서버가 날짜로 계산해 만들기 때문에 회차를 만들거나 바꾸는 API는 없습니다.
회차 목록과 신청서 조회(F-23)가 동작하고, 회차 점검·추천·신청서 제출은 아직 501 틀입니다.
경로의 round 자리에는 회차 번호(1, 2, …)나 오늘이 속한 회차를 뜻하는 current를 넣습니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.api.deps import CurrentAccount, IfMatch, get_current_account
from app.api.responses import error_responses
from app.core.clock import Today
from app.core.db import DbSession
from app.core.errors import NotImplementedYetError
from app.schemas.application import ApplicationRead
from app.schemas.common import JsonPatch, Page, UpdatesRead
from app.schemas.rounds import RecommendationList, RoundCheck, RoundSummary
from app.services import accounts as account_service
from app.services import application as application_service

router = APIRouter(prefix="/accounts/{persona_id}", tags=["rounds"])
_auth = [Depends(get_current_account)]

RoundRef = Annotated[
    str, Path(pattern=r"^(current|[1-9][0-9]?)$", description="회차 번호 또는 current")
]


@router.get("/rounds", summary="회차 목록", responses=error_responses(401, 404))
def list_rounds(db: DbSession, account: CurrentAccount, today: Today) -> Page[RoundSummary]:
    """이 계정의 실업인정 회차 전체를 돌려줍니다. 지난 회차를 다시 볼 때 씁니다.

    각 회차의 상태(지난·지금·앞으로)는 저장된 값이 아니라 오늘 날짜로 계산합니다. 신청서 제출 여부도
    함께 보입니다.
    """
    rounds = account_service.read_rounds(db, account.user_id, today)
    return Page(items=rounds, total=len(rounds))


@router.get(
    "/rounds/current",
    summary="이번 회차 점검",
    dependencies=_auth,
    responses=error_responses(401, 404, 501),
)
def get_current_round() -> RoundCheck:
    """오늘이 속한 회차의 재취업활동 점검 결과를 돌려줍니다.

    필요 건수와 인정 건수, 남은 건수, D-day, 활동별 인정 상태와 경고, 필요한 증빙, 구직 외 활동 누적
    사용 횟수가 들어 있습니다.
    숫자는 모두 규칙 함수가 계산합니다. 아직 회차가 없으면 404 NO_ACTIVE_ROUND. (아직 구현 전이라
    501)
    """
    raise NotImplementedYetError()


@router.get(
    "/rounds/current/recommendations",
    summary="부족한 활동 추천",
    dependencies=_auth,
    responses=error_responses(401, 404, 501),
)
def list_recommendations() -> RecommendationList:
    """이번 회차에 활동이 모자랄 때 증빙이 쉬운 순서로 추천 3개와 기한 문구를 돌려줍니다.

    직업훈련·특강·집단상담 후보에는 고용24 조회 결과(실제 과정·일정)를 붙입니다. (아직 구현 전이라
    501)
    """
    raise NotImplementedYetError()


@router.get(
    "/rounds/{round}/application",
    summary="회차 신청서 조회",
    responses=error_responses(401, 404),
)
def get_application(
    db: DbSession, account: CurrentAccount, round: RoundRef, today: Today
) -> ApplicationRead:
    """회차의 실업인정 신청서를 고용24 화면 순서대로 돌려줍니다. 작성내용 확인 화면도 이 응답으로
    그립니다.

    본인 답변 칸, 인정 활동에서 만든 구직활동 줄, 제출을 막는 항목과 경고, 지금 시각 기준 제출
    방식(submit_mode),
    잠금 사유(취업·산재), 신청인·지급계좌 표시값이 들어 있습니다. round에는 회차 번호나 current를
    넣습니다.

    구직활동 줄은 그 회차 대상기간의 실제 활동에서 만들고(같은 날 2건째는 excluded_rows),
    지난 회차에 답한 통지 방법·실업크레딧은 이번 회차가 비어 있으면 불러옵니다.
    오늘이 속한 회차가 없으면(current) 404 NO_ACTIVE_ROUND, 없는 회차 번호면 404입니다.
    """
    return application_service.read_application(db, account, round, today)


@router.patch(
    "/rounds/{round}/application",
    summary="회차 신청서 고치기 · 제출",
    dependencies=_auth,
    responses=error_responses(401, 404, 409, 422, 501),
)
def patch_application(round: RoundRef, patch: JsonPatch, if_match: IfMatch = None) -> UpdatesRead:
    """JSON Patch로 칸을 고치면 바로 저장됩니다(임시저장 경로는 따로 없음).

    제출은 `/status`를 `submitted`로, `/submit_mode`를 GET이 알려 준 방식(send·attend)으로 보냅니다.
    출석 회차면 `/attend_items`도 보냅니다.
    막는 항목이 남았거나 방식이 다르면 409 CANNOT_SUBMIT, 지난 회차면 409 ROUND_CLOSED, 본인 답변
    칸을 고치려 하면 422입니다.
    (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()
