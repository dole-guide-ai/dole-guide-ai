"""고용24 OpenAPI로 훈련과정과 취업역량 프로그램을 조회하는 라우터입니다.

조건을 비우면 이 계정의 이력서 희망 조건과 관할 센터로 조회합니다. 결과는 저장하지 않고, 외부
API가 실패하면 미리 받아 둔 스냅샷을 씁니다.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentAccount, get_current_account
from app.api.responses import error_responses
from app.core.clock import Now
from app.core.db import DbSession
from app.schemas.trainings import ProgramList, TrainingList
from app.services import trainings as training_service

router = APIRouter(
    prefix="/accounts/{persona_id}", tags=["trainings"], dependencies=[Depends(get_current_account)]
)


@router.get(
    "/trainings",
    summary="국민내일배움카드 훈련과정 조회",
    responses=error_responses(401, 404, 503),
)
def list_trainings(
    db: DbSession,
    account: CurrentAccount,
    now: Now,
    region: str | None = None,
    occupation: str | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> TrainingList:
    """고용24 OpenAPI로 훈련과정을 조회합니다. 조건을 비우면 이 계정 이력서의 희망 직종·지역으로
    조회합니다.

    결과는 저장하지 않으며, 외부 API가 실패하면 미리 받아 둔 스냅샷으로 대체하고 source=snapshot을
    붙입니다.
    스냅샷도 없으면 503 EXTERNAL_UNAVAILABLE입니다. 희망 직종은 과정명 키워드로 찾습니다(직종코드를
    NCS로 바꾸지 않음). 지역은 주소에 그 이름이 들어간 과정만 남깁니다.
    """
    return training_service.list_trainings(
        db, account, region, occupation, page, now, date_from, date_to
    )


@router.get(
    "/programs",
    summary="구직자취업역량 강화프로그램 조회",
    responses=error_responses(401, 404, 503),
)
def list_programs(
    now: Now,
    center: str | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> ProgramList:
    """고용24 OpenAPI로 고용센터의 집단상담·취업특강 일정을 조회합니다. 조건을 비우면 관할 센터로
    조회합니다.

    결과는 저장하지 않고, 실패하면 스냅샷으로 대체합니다. 고용센터 코드 표가 아직 없어 center는
    받기만 하고 쓰지 않습니다.
    from이 있으면 그날부터, to가 있으면 그날까지 시작하는 과정을 찾습니다.
    """
    return training_service.list_programs(date_from, now, date_to, page)
