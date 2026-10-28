"""패널에서 직접 고른 공통코드 칸(희망 직종·희망 지역·경력 직종) → 칸 쓰기와 지울 항목. LLM·DB 없음.

화면은 드롭다운에서 고른 코드(`{code}`)나 이름만 적기(`{name}`)를 보내고, 코드가 맞는지와
칸 값 모양(`{code, name, status, said}`)은 여기서 정합니다(rules/work24_codes).
화면이 상태를 정하지 않습니다.

- 희망 직종은 목록 통째로 받습니다(`/job_preferences/desired_occupations`에 [{code}…]). 같은 코드
  (이름만 적은 값은 같은 이름)의 기존 항목은 경력여부·희망직무내용과 함께 그대로 두고, 새 직종은 새
  항목으로, 목록에서 뺀 직종은 지울 항목으로 돌려줍니다.
- 희망 지역은 칸 하나에 목록이라 고른 지역 목록을 그대로 씁니다.
"""

from dataclasses import dataclass, field
from typing import Any

from app.rules.resume.codes import code_kind_of, name_for_code, name_path_of
from app.rules.resume.fields import OCCUPATIONS_PATH, REGIONS_PATH
from app.rules.resume.items import ItemPicker, same_name
from app.rules.work24_codes import (
    CodeKind,
    chosen_value,
    code_status,
    has_codes,
    said_name,
    with_status,
)
from app.schemas.forms.resume import ResumeData

OCCUPATION_FIELD = "/occupation"


class InvalidCodeError(ValueError):
    """코드표에 없는 코드이거나 모양이 다른 값. 서비스가 422로 바꿉니다."""


@dataclass
class CodeEdit:
    writes: list[tuple[str, Any]] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)  # 지울 항목 경로(`/…/desired_occupations/o2`)


def with_code_status(data: ResumeData) -> ResumeData:
    """희망 직종·경력 직종·희망 지역 값에 상태를 채운 이력서. 예전 값(상태 없음)을 읽을 때."""
    data = data.model_copy(deep=True)
    for f in [
        *(d.occupation for d in data.job_preferences.desired_occupations),
        *(c.occupation for c in data.careers),
    ]:
        f.value = with_status(f.value)
    regions = data.job_preferences.desired_regions
    if isinstance(regions.value, list):
        regions.value = [with_status(r) for r in regions.value]
    return data


def code_kind(path: str) -> CodeKind | None:
    """공통코드로 고르는 칸이면 그 종류. 희망 직종 목록·각 항목, 경력 직종, 희망 지역,
    이름 칸 옆의 코드 칸(자격면허코드·전공코드, rules/resume/codes)."""
    if kind := code_kind_of(path):
        return kind
    if path == REGIONS_PATH:
        return "region"
    if path == OCCUPATIONS_PATH or (
        path.endswith(OCCUPATION_FIELD) and path.startswith((OCCUPATIONS_PATH, "/careers/"))
    ):
        return "occupation"
    return None


def code_edit(data: ResumeData, path: str, value: Any) -> CodeEdit:
    """고른 값 → 칸 쓰기. `code_kind(path)`가 있는 경로만 받습니다."""
    if path == OCCUPATIONS_PATH:
        return _occupations(data, value)
    if path == REGIONS_PATH:
        return CodeEdit(writes=[(path, [_chosen("region", v) for v in _as_list(value)])])
    if (
        value is None
    ):  # 경력 직종·자격면허코드 등 비우기. 짝인 이름 칸(자격면허명·전공)도 같이 비웁니다.
        name_path = name_path_of(path)
        return CodeEdit(writes=[(path, None), *([(name_path, None)] if name_path else [])])
    kind = code_kind(path) or "occupation"
    if code_kind_of(path) and not has_codes(kind):
        # 코드표가 아직 없는 자격면허·전공은 고를 코드가 없으니 이름만 적은 값으로 코드 칸도
        # 같이 씁니다(예전 코드가 새 이름과 어긋나게 남지 않게).
        chosen = _chosen(kind, value)
        return CodeEdit(writes=[(path, chosen), *name_for_code(path, chosen)])
    chosen = _chosen(kind, value)
    # 자격면허·전공은 이름 칸도 고른 공식 이름으로 같이 씁니다(짝: rules/resume/codes).
    return CodeEdit(writes=[(path, chosen), *name_for_code(path, chosen)])


def _occupations(data: ResumeData, values: Any) -> CodeEdit:
    chosen = [_chosen("occupation", v) for v in _as_list(values)]
    existing = data.job_preferences.desired_occupations
    picker = ItemPicker(data)
    edit = CodeEdit()
    kept: set[str] = set()
    for value in chosen:
        same = next(
            (d for d in existing if d.item_id not in kept and _same(d.occupation.value, value)),
            None,
        )
        if same is not None:
            kept.add(same.item_id)
            # 같은 직종으로 끝난 항목은 그대로 둡니다(말한 이름도 유지). 고르기 전이었으면 씁니다.
            if code_status(same.occupation.value) != code_status(value):
                edit.writes.append((f"{OCCUPATIONS_PATH}/{same.item_id}{OCCUPATION_FIELD}", value))
            continue
        item_id = picker.new_id("desired_occupations")
        edit.writes.append((f"{OCCUPATIONS_PATH}/{item_id}{OCCUPATION_FIELD}", value))
    edit.removed = [f"{OCCUPATIONS_PATH}/{d.item_id}" for d in existing if d.item_id not in kept]
    return edit


def _same(current: Any, chosen: dict[str, Any]) -> bool:
    """같은 직종인지: 둘 다 코드가 있으면 코드로, 아니면 이름(공식 이름·말한 이름)으로 봅니다.
    같은 항목이면 경력여부·희망직무내용을 지키고 직종 값만 바꿉니다."""
    if not isinstance(current, dict):
        return False
    if current.get("code") and chosen.get("code"):
        return current["code"] == chosen["code"]
    # 한쪽만 코드가 있으면(고르기 전 항목에 코드를 고름, 고른 직종을 이름만 적기로 바꿈)
    # 이름으로 봅니다.
    names = {current.get("name"), said_name(current)}
    return any(same_name(n, chosen.get("name")) for n in names if n)


def _chosen(kind: CodeKind, raw: Any) -> dict[str, Any]:
    if (value := chosen_value(kind, raw)) is None:
        raise InvalidCodeError(kind)
    return value


def _as_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise InvalidCodeError("list")
    return value
