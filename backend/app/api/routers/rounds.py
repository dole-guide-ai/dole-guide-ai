"""실업인정 회차와 회차별 신청서를 다루는 라우터입니다.

회차는 서버가 날짜로 계산해 만들기 때문에 회차를 만들거나 바꾸는 API는 없습니다.
회차 목록과 신청서 조회·제출(F-23·F-27), 부족한 활동 추천(F-19)이 동작하고,
경로의 round 자리에는 회차 번호(1, 2, …)나 오늘이 속한 회차를 뜻하는 current를 넣습니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from app.api.deps import CurrentAccount, IfMatch, get_current_account
from app.api.responses import error_responses
from app.core.clock import Now, Today
from app.core.db import DbSession
from app.core.etag import etag
from app.schemas.application import ApplicationRead
from app.schemas.common import JsonPatch, Page, UpdatesRead
from app.schemas.rounds import RecommendationList, RoundCheck, RoundSummary
from app.services import accounts as account_service
from app.services import application as application_service
from app.services import recommendations as recommendation_service
from app.services import rounds as round_service

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
    responses=error_responses(401, 404),
)
def get_current_round(db: DbSession, account: CurrentAccount, today: Today) -> RoundCheck:
    """오늘이 속한 회차의 재취업활동 점검 결과를 돌려줍니다.

    필요 건수와 인정 건수, 남은 건수, D-day, 활동별 인정 상태와 경고, 필요한 증빙, 구직 외 활동 누적
    사용 횟수가 들어 있습니다.
    숫자는 모두 규칙 함수(`check_round`, 상세기획 2-2.6)가 계산합니다. `status`는 회차 상태,
    `check_status`는 충족(satisfied)·부족(short)·확인 필요(needs_check)입니다. 일반 수급자 8차부터는
    `weeks`에 7일마다의 구직활동 수가 들어갑니다. 아직 회차가 없으면 404 NO_ACTIVE_ROUND.
    """
    return round_service.read_current(db, account.user_id, today)


@router.get(
    "/rounds/current/recommendations",
    summary="부족한 활동 추천",
    responses=error_responses(401, 404),
)
def list_recommendations(db: DbSession, account: CurrentAccount, now: Now) -> RecommendationList:
    """이번 회차에 활동이 모자랄 때 증빙이 쉬운 순서로 추천 최대 3개와 기한 문구를 돌려줍니다.

    부족하지 않으면 빈 목록입니다. 오늘이 속한 회차가 없으면 404 NO_ACTIVE_ROUND.
    고른 추천은 `POST …/activities`에 `recommendation_id`만 보내 예정 활동으로 넣습니다.
    """
    return recommendation_service.list_recommendations(db, account, now)


@router.get(
    "/rounds/{round}/application",
    summary="회차 신청서 조회",
    responses=error_responses(401, 404),
)
def get_application(
    db: DbSession, account: CurrentAccount, round: RoundRef, now: Now, response: Response
) -> ApplicationRead:
    """회차의 실업인정 신청서를 고용24 화면 순서대로 돌려줍니다. 작성내용 확인 화면도 이 응답으로
    그립니다.

    본인 답변 칸, 인정 활동에서 만든 구직활동 줄, 제출을 막는 항목과 경고, 지금 시각 기준 제출
    방식(submit_mode),
    잠금 사유(취업·산재), 신청인·지급계좌 표시값이 들어 있습니다. round에는 회차 번호나 current를
    넣습니다.

    구직활동 줄은 그 회차 대상기간의 실제 활동에서 만들고(같은 날 2건째는 excluded_rows),
    지난 회차에 답한 통지 방법·실업크레딧은 이번 회차가 비어 있으면 불러옵니다.
    제출 방식(submit_mode)은 실제 지금 시각(KST)으로 정합니다: 출석 회차 attend, 인정일 전 preview,
    당일 17시 전 send, 17~18시 visit_today, 그 뒤 change. 막는 항목이 없고 send·attend일 때만
    can_submit이 true이며, 경고(활동 부족·증빙 없음·실업크레딧)는 제출을 막지 않습니다.
    오늘이 속한 회차가 없으면(current) 404 NO_ACTIVE_ROUND, 없는 회차 번호면 404입니다.
    """
    application = application_service.read_application(db, account, round, now)
    # 제출 PATCH는 이 값을 If-Match로 돌려보냅니다 (다른 탭에서 먼저 제출했으면 409).
    response.headers["ETag"] = etag(application.lock_version)
    return application


@router.patch(
    "/rounds/{round}/application",
    summary="회차 신청서 제출",
    responses=error_responses(401, 404, 409, 422),
)
def patch_application(
    db: DbSession,
    account: CurrentAccount,
    round: RoundRef,
    patch: JsonPatch,
    now: Now,
    if_match: IfMatch,
) -> UpdatesRead:
    """신청서를 제출(모의)합니다. 본인 답변은 대화로만 채우고 받을 때마다 바로 저장됩니다.

    - 제출: `/status`를 `submitted`로, `/submit_mode`를 GET이 알려 준 방식(send·attend)으로
      보냅니다. 출석 회차면 `/attend_items`에 `["id_card", "eligibility_card"]`(준비물 체크)도.
    - 방식이 다르거나(인정일 전 preview 등) 막는 항목이 남았거나 준비물을 체크하지 않았으면
      409 CANNOT_SUBMIT, 이미 제출했으면 409 APPLICATION_LOCKED, 지난 회차면 409 ROUND_CLOSED,
      If-Match가 GET의 ETag와 다르면 409 VERSION_CONFLICT입니다.
    - 본인 답변 칸을 고치려 하면 422 USER_ANSWER_ONLY, 제출 칸과 다른 칸을 섞으면 422입니다.

    제출은 status만 바꾸고 본인 답변은 지우지 않습니다. 응답 entry는 바뀐 첫 화면입니다.
    """
    return application_service.patch_application(db, account, round, patch, if_match, now)
