"""이력서를 조회하고 칸을 고치거나 저장하는 라우터입니다.

저장은 따로 경로가 없고, PATCH로 status를 saved(저장)나 draft(다시 고치기)로 바꾸는 방식입니다.
실제 처리는 services/resume.py가 합니다.
"""

from fastapi import APIRouter, Depends, Response

from app.api.deps import CurrentAccount, IfMatch, get_current_account
from app.api.responses import error_responses
from app.core.clock import Now
from app.core.db import DbSession
from app.core.etag import etag
from app.schemas.common import JsonPatch, UpdatesRead
from app.schemas.resume import ResumeRead
from app.services import resume as resume_service

router = APIRouter(
    prefix="/accounts/{persona_id}", tags=["resume"], dependencies=[Depends(get_current_account)]
)


@router.get("/resume", summary="이력서 조회", responses=error_responses(401, 404))
def get_resume(db: DbSession, account: CurrentAccount, response: Response) -> ResumeRead:
    """고용24 이력서 양식대로 채워진 값과 칸마다의 상태(출처·확인 여부), 꼭 묻는 5개 항목의 완성도,
    다음에 물을 질문, 저장 가능 여부, 맨 위 기본정보(고용24 회원정보에서 연동) 표시값을 돌려줍니다.
    아직 이력서가 없으면 빈 초안(lock_version 0)입니다.
    응답의 ETag는 고칠 때 If-Match 헤더로 보냅니다.
    """
    resume = resume_service.read_resume(db, account)
    response.headers["ETag"] = etag(resume.lock_version)
    return resume


@router.patch(
    "/resume", summary="이력서 칸 고치기 · 저장", responses=error_responses(401, 404, 409, 422)
)
def patch_resume(
    db: DbSession, account: CurrentAccount, patch: JsonPatch, now: Now, if_match: IfMatch = None
) -> UpdatesRead:
    """JSON Patch로 칸을 고치거나, 이력서를 저장합니다.

    - 칸 고치기: `[{"op": "replace", "path": "/careers/c1/company_name", "value": "OO물산"}]`. 여러
      칸을 한 번에 보낼 수 있고, 고친 칸은 확인됨·직접 입력이 됩니다. 응답 updates는
      바뀐 칸들입니다.
    - 저장: `[{"op": "replace", "path": "/status", "value": "saved"}]`. 꼭 묻는 5개가 다 차고 확인
      필요가 없어야 하며, 아니면 409 RESUME_NOT_READY. 저장하면 단계가 온라인 교육으로 넘어가고,
      응답 entry에 바뀐 첫 화면(저장 안내·고용24 입력 안내 포함)이 옵니다.
    - 다시 고치기: `/status`를 `draft`로. `/status`는 다른 칸과 함께 보낼 수 없습니다(422).

    If-Match가 GET의 ETag와 다르면(다른 탭에서 먼저 고침) 409 VERSION_CONFLICT입니다.
    """
    return resume_service.patch_resume(db, account, patch, if_match, now)
