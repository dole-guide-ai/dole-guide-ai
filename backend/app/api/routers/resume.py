"""이력서를 조회하고 칸을 고치거나 저장하는 라우터입니다.

저장은 따로 경로가 없고, PATCH로 status를 saved(저장)나 draft(다시 고치기)로 바꾸는 방식입니다.
아직 틀만 있어 501을 돌려주며, 이력서 기능을 구현할 때 서비스·레포지토리를 붙여 채웁니다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import IfMatch, get_current_account
from app.api.responses import error_responses
from app.core.errors import NotImplementedYetError
from app.schemas.common import JsonPatch, UpdatesRead
from app.schemas.resume import ResumeRead

router = APIRouter(
    prefix="/accounts/{persona_id}", tags=["resume"], dependencies=[Depends(get_current_account)]
)


@router.get("/resume", summary="이력서 조회", responses=error_responses(401, 404, 501))
def get_resume() -> ResumeRead:
    """고용24 이력서 양식대로 채워진 값과 칸마다의 상태(출처·확인 여부), 꼭 묻는 5개 항목의 완성도,
    다음에 물을 질문, 저장 가능 여부, 맨 위 기본정보(고용24 회원정보에서 연동) 표시값을 돌려줍니다.
    응답의 ETag는 고칠 때 If-Match 헤더로 보냅니다. (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()


@router.patch(
    "/resume", summary="이력서 칸 고치기 · 저장", responses=error_responses(401, 404, 409, 422, 501)
)
def patch_resume(patch: JsonPatch, if_match: IfMatch = None) -> UpdatesRead:
    """JSON Patch로 칸을 고치거나, 이력서를 저장합니다.

    - 칸 고치기: `[{"op": "replace", "path": "/careers/c1/company_name", "value": "OO물산"}]`. 여러
      칸을 한 번에 보낼 수 있습니다.
    - 저장: `[{"op": "replace", "path": "/status", "value": "saved"}]`. 꼭 묻는 5개가 다 차고 확인
      필요가 없어야 하며, 아니면 409 RESUME_NOT_READY.
    - 다시 고치기: `/status`를 `draft`로. `/status`는 다른 칸과 함께 보낼 수 없습니다(422).

    If-Match가 GET의 ETag와 다르면(다른 탭에서 먼저 고침) 409 VERSION_CONFLICT입니다. (아직 구현
    전이라 501)
    """
    raise NotImplementedYetError()
