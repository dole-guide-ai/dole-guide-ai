"""화면에서 희망 지역·직종·자격면허·전공을 직접 고를 때 쓰는 고용24 공통코드 조회 서비스 (F-12).

찾는 기준은 대화와 같아야 하므로 rules/work24_codes 한 곳에 두고 여기서는 부르기만 합니다.
라우터는 rules를 직접 읽지 않으므로 코드 종류 타입(CodeKind)도 여기서 내보냅니다.
"""

from app.rules import work24_codes
from app.rules.work24_codes import CodeKind
from app.schemas.codes import CodeRead


def list_regions() -> list[CodeRead]:
    """시·도와 시·군·구 전체. 화면은 parent로 2단계를 만듭니다."""
    return list(work24_codes.load_codes()["region"])


def search(kind: CodeKind, q: str, limit: int) -> list[CodeRead]:
    """이름 검색(직종·자격면허·전공). 코드표가 아직 없는 종류는 빈 목록입니다."""
    return work24_codes.lookup_code(kind, q, limit)
