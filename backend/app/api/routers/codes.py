"""화면에서 희망 지역·직종을 직접 고를 때 쓰는 고용24 공통코드 조회 라우터입니다 (F-12).

계정과 무관한 기준표라 /accounts 밖에 두고, 방문자 토큰만 확인합니다.
실제 처리는 services/work24_codes.py가 합니다.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentVisitor
from app.api.responses import error_responses
from app.schemas.codes import CodeRead
from app.schemas.common import Page
from app.services import work24_codes

router = APIRouter(prefix="/codes", tags=["codes"])


@router.get("/regions", summary="지역 코드 전체", responses=error_responses(401))
def list_regions(_: CurrentVisitor) -> Page[CodeRead]:
    """시·도와 시·군·구 전체(약 285개)를 한 번에 돌려줍니다. 화면은 parent로 2단계를 만듭니다."""
    items = work24_codes.list_regions()
    return Page(items=items, total=len(items))


SearchText = Annotated[str, Query(max_length=50, description="이름 일부. 띄어쓰기 무시")]
SearchLimit = Annotated[int, Query(ge=1, le=20)]


def _page(kind: work24_codes.CodeKind, q: str, limit: int) -> Page[CodeRead]:
    items = work24_codes.search(kind, q, limit)
    return Page(items=items, total=len(items))


@router.get("/occupations", summary="세부 직종 이름 검색", responses=error_responses(401, 422))
def search_occupations(_: CurrentVisitor, q: SearchText, limit: SearchLimit = 10) -> Page[CodeRead]:
    """이름에 q가 들어간 세부 직종을 짧은 이름부터 limit개 돌려줍니다(자동완성)."""
    return _page("occupation", q, limit)


@router.get("/licenses", summary="자격면허 이름 검색", responses=error_responses(401, 422))
def search_licenses(_: CurrentVisitor, q: SearchText, limit: SearchLimit = 10) -> Page[CodeRead]:
    """고용24 자격면허코드(dtlGb=3) 검색. 코드표를 받기 전에는 빈 목록입니다."""
    return _page("license", q, limit)


@router.get("/majors", summary="전공 이름 검색", responses=error_responses(401, 422))
def search_majors(_: CurrentVisitor, q: SearchText, limit: SearchLimit = 10) -> Page[CodeRead]:
    """고용24 전공코드(dtlGb=6) 검색. 코드표를 받기 전에는 빈 목록입니다."""
    return _page("major", q, limit)
