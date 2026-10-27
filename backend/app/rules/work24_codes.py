"""고용24 공통코드(지역·직종·자격면허·전공)로 말한 이름의 코드 후보를 찾고, 이력서 칸 값을 만듭니다.

코드는 고정 기준표라 DB에 넣지 않고 data/reference/work24_codes.json을 처음 쓸 때 한 번 읽어
메모리에 둡니다. 실행 중에는 고용24 API를 부르지 않습니다. 코드가 바뀌면 사람이
scripts/fetch_work24_codes.py를 돌려 JSON을 다시 만듭니다.

대화의 저장 계획·질문(rules/resume)과 화면 직접 고르기(GET /codes/occupations)가 같은 기준을 씁니다.
- 코드 칸 값은 종류와 관계없이 `{code, name, status, said}`입니다. `said`는 사용자가 말한 이름이고,
  후보를 고르면 `name`은 고용24 공식 이름이 됩니다.
- 말한 이름이 공식 이름과 하나만 똑같으면 바로 확정하고, 아니면 후보를 골라야 합니다.
- 코드표에 아직 없는 종류(인증키로 받기 전)는 고를 수 없으므로 끝난 것으로 봅니다(code_settled).
  코드표를 받으면 같은 규칙으로 고르기가 켜집니다.
"""

import csv
import json
import re
from functools import cache, lru_cache
from pathlib import Path
from typing import Any, Literal

from app.schemas.codes import CodeRead
from app.schemas.forms.resume import CodeStatus

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"
CODES_JSON = REFERENCE_DIR / "work24_codes.json"
# 흔히 쓰는 말 → 고용24 공식 이름 짝(사람이 검수해 적음). 코드표 이름에 말이 없을 때 씁니다.
ALIASES_CSV = REFERENCE_DIR / "code_aliases.csv"
AI_CANDIDATES = 3
# 말 전체로 못 찾으면 낱말로 다시 찾습니다. 한 글자 낱말("일")은 너무 많이 걸려 쓰지 않습니다.
MIN_WORD = 2
# 이름 속 "(… 제외)"는 그 직종이 아닌 일을 적은 설명이라 찾을 글자로 보지 않습니다.
# 예: "건물 보수원 및 영선원(아파트 기계·전기 시설관리 제외)"는 "시설관리"로 찾지 않음
_EXCLUDED = re.compile(r"\([^)]*제외\)")
_WORD_SPLIT = re.compile(r"[\s·,/]+")

CodeKind = Literal["occupation", "region", "license", "major"]
# 코드 종류 → work24_codes.json의 키 (고용24 공통코드 dtlGb 2·1·3·6)
CODE_KEYS: dict[CodeKind, str] = {
    "occupation": "occupations",
    "region": "regions",
    "license": "licenses",
    "major": "majors",
}


@lru_cache(maxsize=1)
def load_codes(path: Path = CODES_JSON) -> dict[CodeKind, tuple[CodeRead, ...]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {kind: tuple(CodeRead(**c) for c in raw.get(key, [])) for kind, key in CODE_KEYS.items()}


def has_codes(kind: CodeKind) -> bool:
    """이 종류의 코드표가 있는지. 없으면 고르게 하지 않고 말한 이름만 둡니다."""
    return bool(load_codes()[kind])


def lookup_code(kind: CodeKind, text: str, limit: int = AI_CANDIDATES) -> list[CodeRead]:
    """이름에 말이 들어간 코드를 짧은 이름부터 limit개. 띄어쓰기는 무시합니다.

    직종은 고용24 이력서에서 고르는 세부 직종(3단계)만, 지역은 시·군·구를 먼저 돌려줍니다.
    같은 코드가 여러 분류에 걸려 있어도 한 번만 냅니다. 말 전체로 못 찾으면 낱말별로 찾습니다.
    """
    hits = _unique([*_aliased(kind, text), *_find(kind, text)])
    if not hits:
        words = [w for w in _WORD_SPLIT.split(text) if len(w) >= MIN_WORD]
        hits = _unique(c for w in words for c in _find(kind, w))
    return hits[:limit]


def region_code(text: str) -> CodeRead | None:
    """말한 지역(서울, 강남구, 경기 부천시) → 지역 코드 하나. 똑같은 이름이 하나면 그것, 아니면
    찾은 첫 후보(시·군·구 먼저). "중구"처럼 똑같은 이름이 여러 시·도에 있거나 못 찾으면 None.
    훈련 검색처럼 지역 하나로 거를 때 씁니다."""
    same = [c for c in _find("region", text) if _same_name("region", c.name, text)]
    if len(same) > 1:
        return None
    if same:
        return same[0]
    hits = lookup_code("region", text, 1)
    return hits[0] if hits else None


def code_by_id(kind: CodeKind, code: str) -> CodeRead | None:
    """고를 수 있는 코드 하나(_choosable)."""
    return _by_id()[kind].get(code)


def chosen_value(kind: CodeKind, raw: Any) -> dict[str, Any] | None:
    """화면에서 고른 값 → 칸 값. `{code}`는 코드표의 이름으로 확정하고, `{name}`(코드 없음)은
    이름만 적은 값입니다. 코드표에 없는 코드나 모양이 다른 값이면 None(저장하지 않음)."""
    if not isinstance(raw, dict):
        return None
    if raw.get("code"):
        code = code_by_id(kind, str(raw["code"]))
        return picked(code, str(raw.get("said") or code.name)) if code else None
    name = str(raw.get("name") or "").strip()
    return name_only(name) if name else None


def match_code(kind: CodeKind, said: str) -> dict[str, Any]:
    """말한 이름 → 칸 값. 공식 이름이 똑같은 코드가 하나면 확정, 아니면 후보를 고를 차례."""
    said = said.strip()
    same = [c for c in _find(kind, said) if _same_name(kind, c.name, said)] or _aliased(kind, said)
    if len(same) == 1:  # 공식 이름과 똑같거나, 짝 목록이 이름 하나로 정해 둔 말(바뀐 자격 이름 등)
        return picked(same[0], said)
    return {"code": None, "name": said, "status": CodeStatus.NEEDS_CONFIRMATION.value, "said": said}


def picked(code: CodeRead, said: str) -> dict[str, Any]:
    """후보 중에서 고른 값."""
    return {
        "code": code.code,
        "name": code.name,
        "status": CodeStatus.CONFIRMED.value,
        "said": said,
    }


def name_only(said: str) -> dict[str, Any]:
    """후보가 다 맞지 않을 때 말한 이름만 저장합니다 (고용24 입력 때 목록에서 고르기)."""
    said = said.strip()
    return {"code": None, "name": said, "status": CodeStatus.NAME_ONLY.value, "said": said}


def code_status(value: Any) -> CodeStatus | None:
    """칸 값의 확정 상태. 상태가 없던 예전 값은 코드가 있으면 확정, 없으면 고를 차례로 봅니다."""
    if not isinstance(value, dict) or not value.get("name"):
        return None
    status = value.get("status")
    if status in CodeStatus:
        return CodeStatus(status)
    return CodeStatus.CONFIRMED if value.get("code") else CodeStatus.NEEDS_CONFIRMATION


def with_status(value: Any) -> Any:
    """상태가 없던 예전 값에 상태를 채웁니다(code_status 기준). 화면이 상태를 짐작하지 않게."""
    status = code_status(value)
    if status is None or value.get("status") == status:
        return value
    return {**value, "status": status.value}


def code_settled(kind: CodeKind, value: Any) -> bool:
    """꼭 채울 칸 판정용: 코드를 골랐거나 이름만 적기로 했거나, 이 종류의 코드표가 아직 없음."""
    return not has_codes(kind) or code_done(value)


def code_done(value: Any) -> bool:
    """고용24에 그대로 옮길 수 있는 값인지: 코드를 골랐거나, 이름만 적기로 했거나."""
    status = code_status(value)
    if status == CodeStatus.CONFIRMED:
        return bool(value.get("code"))
    return status == CodeStatus.NAME_ONLY


def said_name(value: Any) -> str | None:
    """사용자가 말한 이름(예전 값은 이름). 같은 말을 다시 했는지 볼 때 씁니다."""
    if not isinstance(value, dict):
        return None
    return value.get("said") or value.get("name")


@lru_cache(maxsize=1)
def _by_id() -> dict[CodeKind, dict[str, CodeRead]]:
    return {kind: {c.code: c for c in _choosable(kind)} for kind in CODE_KEYS}


@cache
def _choosable(kind: CodeKind) -> tuple[CodeRead, ...]:
    """이력서에서 고를 수 있는 코드. 지역은 시·도와 시·군·구 모두, 나머지는 분류가 아닌 맨 아래
    단계(다른 코드의 상위가 아닌 코드)만 고릅니다. 직종이면 세부 직종(3단계)입니다."""
    codes = load_codes()[kind]
    if kind == "region":
        return codes
    parents = {c.parent for c in codes}
    return tuple(c for c in codes if c.code not in parents)


@cache
def _aliases() -> dict[tuple[str, str], tuple[str, ...]]:
    """(종류, 말) → 공식 이름들. 파일이 없으면 빈 목록."""
    if not ALIASES_CSV.exists():
        return {}
    out: dict[tuple[str, str], list[str]] = {}
    with ALIASES_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.setdefault((row["kind"], _compact(row["said"])), []).append(row["name"])
    return {key: tuple(names) for key, names in out.items()}


def _aliased(kind: CodeKind, text: str) -> list[CodeRead]:
    """짝 목록의 공식 이름 → 고를 수 있는 코드(이름이 똑같은 것)."""
    names = _aliases().get((kind, _compact(text)), ())
    by_name = {c.name: c for c in reversed(_choosable(kind))}  # 같은 이름이면 앞 코드
    return [by_name[n] for n in names if n in by_name]


def _find(kind: CodeKind, text: str) -> list[CodeRead]:
    needle = _compact(text)
    if not needle:
        return []
    codes = _choosable(kind)
    hits = [c for c in codes if needle in _compact(_EXCLUDED.sub("", c.name))]
    hits.sort(key=lambda c: (-c.depth, len(c.name), c.code))
    return _unique(hits)


def _same_name(kind: CodeKind, name: str, said: str) -> bool:
    """공식 이름과 똑같이 말했는지. 지역은 시·도를 빼고 말해도 같다고 봅니다("노원구")."""
    names = {name}
    if kind == "region":
        names.add(name.split(" ", 1)[-1])
    return _compact(said) in {_compact(n) for n in names}


def _unique(codes: Any) -> list[CodeRead]:
    seen: set[str] = set()
    out = []
    for c in codes:
        if c.code not in seen and c.name not in seen:
            seen |= {c.code, c.name}
            out.append(c)
    return out


def _compact(text: str) -> str:
    return "".join(text.split())
