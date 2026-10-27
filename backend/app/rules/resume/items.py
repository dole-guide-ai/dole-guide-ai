"""반복 항목(경력·학력·자격증·희망 직종)에서 이번 쓰기가 어느 항목인지 정합니다. LLM·DB 없음.

같은 회사·자격증·직종을 다시 말하거나 불러와도 새 항목을 만들지 않고 그 항목을 고칩니다(멱등).
대화(rules/resume/facts)와 고용24 불러오기(services/imports)가 이 한 곳의 기준을 씁니다.

- 섹션마다 "같은 항목"을 가르는 값(`SECTIONS`의 keys)이 있고, 값은 공백·회사 표기를 빼고 비교합니다.
- 한 번의 쓰기 계획 안에서 새로 만든 항목도 기억해, 새 항목 둘이 같은 id로 합쳐지지 않게 합니다.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.rules.resume.fields import occupation_name
from app.schemas.forms.resume import ResumeData


@dataclass(frozen=True)
class Section:
    path: str  # 이력서 안 목록 위치(`/careers`)
    prefix: str  # 새 항목 id 앞머리(c1, e1 …)
    items: Callable[[ResumeData], list[Any]]
    # 같은 항목인지 가르는 값들. 하나라도 같으면 같은 항목(예: 학력은 학교 이름이나 학력 종류).
    keys: tuple[Callable[[Any], Any], ...]


SECTIONS: dict[str, Section] = {
    "careers": Section("/careers", "c", lambda d: d.careers, (lambda c: c.company_name.value,)),
    "education": Section(
        "/education",
        "e",
        lambda d: d.education,
        (lambda e: e.school_name.value, lambda e: e.education_level.value),
    ),
    "certifications": Section(
        "/certifications", "q", lambda d: d.certifications, (lambda q: q.certificate_name.value,)
    ),
    "desired_occupations": Section(
        "/job_preferences/desired_occupations",
        "o",
        lambda d: d.job_preferences.desired_occupations,
        (lambda o: occupation_name(o.occupation),),
    ),
}

# 회사 표기 차이("(주)OO", "OO 주식회사", "㈜OO")와 공백은 같은 이름으로 봅니다.
_NAME_NOISE = re.compile(r"\s|\(주\)|㈜|주식회사")


def same_name(a: Any, b: Any) -> bool:
    left, right = norm(a), norm(b)
    return bool(left) and left == right


def norm(value: Any) -> str:
    return _NAME_NOISE.sub("", str(value or ""))


@dataclass(frozen=True)
class Pick:
    item_id: str | None  # None이면 쓰지 않음(없는 item_id이거나 개수 한도가 참)
    is_new: bool
    full: bool = False  # 새 항목을 만들어야 하는데 한도(limit)를 넘음


@dataclass
class ItemPicker:
    """한 번의 쓰기 계획 동안 항목을 고릅니다. 이번에 새로 정한 항목도 기억합니다."""

    data: ResumeData
    # 섹션 → 이번에 새로 만든 항목 [(item_id, 같은 항목을 가르는 값들)]
    planned: dict[str, list[tuple[str, tuple[Any, ...]]]] = field(default_factory=dict)

    def pick(
        self,
        section: str,
        *,
        item_id: str | None = None,
        values: tuple[Any, ...] = (),
        new_id: str | None = None,
        limit: int | None = None,
    ) -> Pick:
        """1) 모델이 준 item_id 2) 같은 값의 기존·이번 항목 3) 새 항목 순서로 고릅니다.

        `values`는 섹션 keys와 같은 순서의 값입니다(빈 값은 비교하지 않음).
        `new_id`를 주면 새 항목에 그 id를 씁니다(불러오기의 `imp_…`).
        `limit`을 넘는 새 항목은 만들지 않습니다(희망 직종은 고용24에서 3개까지).
        """
        spec = SECTIONS[section]
        existing = spec.items(self.data)
        planned = self.planned.setdefault(section, [])
        if item_id:
            known = {i.item_id for i in existing} | {pid for pid, _ in planned}
            return Pick(item_id, False) if item_id in known else Pick(None, False)
        for item in existing:
            if _matches(tuple(key(item) for key in spec.keys), values):
                return Pick(item.item_id, False)
        for pid, planned_values in planned:
            if _matches(planned_values, values):
                return Pick(pid, False)
        if limit is not None and len(existing) + len(planned) >= limit:
            return Pick(None, True, full=True)
        chosen = new_id or self._next_id(spec, existing, planned)
        planned.append((chosen, values))
        return Pick(chosen, True)

    @staticmethod
    def _next_id(spec: Section, existing: list[Any], planned: list[tuple[str, Any]]) -> str:
        used = {i.item_id for i in existing} | {pid for pid, _ in planned}
        n = len(used) + 1
        while f"{spec.prefix}{n}" in used:
            n += 1
        return f"{spec.prefix}{n}"


def new_item_id(data: ResumeData, section: str) -> str:
    """이 섹션에 새로 만들 항목 id. 쓰인 id를 건너뜁니다(지운 id 자리에 덮어쓰지 않게)."""
    spec = SECTIONS[section]
    return ItemPicker._next_id(spec, spec.items(data), [])


def _matches(item_values: tuple[Any, ...], values: tuple[Any, ...]) -> bool:
    return any(same_name(a, b) for a, b in zip(item_values, values, strict=False))
