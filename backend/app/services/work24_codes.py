"""고용24 공통코드(지역·직종)를 읽고, 말한 직종·지역으로 코드 후보를 찾는 서비스입니다.

코드는 고정 기준표라 DB에 넣지 않고 data/reference/work24_codes.json을 처음 쓸 때 한 번 읽어
메모리에 둡니다. 실행 중에는 고용24 API를 부르지 않습니다. 코드가 바뀌면 사람이
scripts/fetch_work24_codes.py를 돌려 JSON을 다시 만듭니다.
대화 중 AI(후보 3개)와 화면 직접 고르기(GET /codes/occupations)가 같은 lookup_code를 씁니다.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.schemas.codes import CodeRead
from app.schemas.forms.resume import OccupationStatus

CODES_JSON = Path(__file__).resolve().parents[2] / "data" / "reference" / "work24_codes.json"
AI_CANDIDATES = 3

CodeKind = Literal["occupation", "region"]


@lru_cache(maxsize=1)
def load_codes(path: Path = CODES_JSON) -> dict[CodeKind, tuple[CodeRead, ...]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "region": tuple(CodeRead(**c) for c in raw["regions"]),
        "occupation": tuple(CodeRead(**c) for c in raw["occupations"]),
    }


def list_regions() -> list[CodeRead]:
    """시·도와 시·군·구 전체. 화면은 parent로 2단계를 만듭니다."""
    return list(load_codes()["region"])


def lookup_code(kind: CodeKind, text: str, limit: int = AI_CANDIDATES) -> list[CodeRead]:
    """이름에 말이 들어간 코드를 짧은 이름부터 limit개. 띄어쓰기는 무시합니다.

    직종은 고용24 이력서에서 고르는 세부 직종(3단계)만, 지역은 시·군·구를 먼저 돌려줍니다.
    """
    needle = "".join(text.split())
    if not needle:
        return []
    codes = load_codes()[kind]
    if kind == "occupation":
        codes = tuple(c for c in codes if c.depth == 3)
    hits = [c for c in codes if needle in "".join(c.name.split())]
    hits.sort(key=lambda c: (-c.depth, len(c.name), c.code))
    return hits[:limit]


def name_only(text: str) -> dict[str, str | None]:
    """후보가 다 맞지 않을 때 말한 이름만 저장합니다 (고용24 입력 때 목록에서 고르기)."""
    return {"code": None, "name": text.strip(), "status": OccupationStatus.NAME_ONLY}
