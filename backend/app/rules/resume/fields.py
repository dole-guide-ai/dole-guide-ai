"""이력서 칸 하나의 상태를 읽는 함수. 다른 이력서 규칙 모듈이 함께 씁니다.

"확인 필요"는 AI·코드가 바꾼 값(extracted + transformed)이나 서로 다른 값(conflict)입니다.
"""

from typing import Any

from app.schemas.common import EvidenceKind, FieldEvidence, FieldSource, FieldStatus, FormField
from app.schemas.forms.resume import EducationLevel
from app.schemas.resume import FieldWrite


def is_filled(f: FormField) -> bool:
    return f.status not in (FieldStatus.MISSING, FieldStatus.REJECTED) and f.value not in (
        None,
        "",
        [],
    )


def needs_check(f: FormField) -> bool:
    """확인 필요 칩 (2-0.6): 바꾼 값이거나 서로 다른 값."""
    return f.status == FieldStatus.CONFLICT or (f.status == FieldStatus.EXTRACTED and f.transformed)


def form_fields(node: Any, path: str = "") -> list[tuple[str, FormField]]:
    """모든 칸을 `/careers/c1/company_name` 경로와 함께 펼칩니다."""
    if isinstance(node, FormField):
        return [(path, node)]
    if isinstance(node, list):
        return [p for item in node for p in form_fields(item, f"{path}/{item.item_id}")]
    out: list[tuple[str, FormField]] = []
    for name in type(node).model_fields:
        if name != "item_id":
            out += form_fields(getattr(node, name), f"{path}/{name}")
    return out


def no_check(node: Any) -> bool:
    return not any(needs_check(f) for _, f in form_fields(node))


def occupation_value(f: FormField) -> dict[str, Any]:
    return f.value if isinstance(f.value, dict) else {}


def occupation_name(f: FormField) -> str | None:
    """직종 칸 값 {code, name, status, said}에서 이름. 모양이 다르면 None."""
    return occupation_value(f).get("name")


def as_list(f: FormField) -> list[Any]:
    return f.value if isinstance(f.value, list) else []


def education_rank(level: Any) -> int:
    levels = list(EducationLevel)
    return levels.index(EducationLevel(level)) if level in levels else -1


def confirmed(value: Any) -> FormField:
    return FormField(value=value, status=FieldStatus.CONFIRMED, source=FieldSource.AUTO)


def suggested(value: Any, note: str) -> FormField:
    return FormField(
        value=value,
        status=FieldStatus.EXTRACTED,
        source=FieldSource.AUTO,
        transformed=True,
        evidence=FieldEvidence(kind=EvidenceKind.COMPUTED, note=note),
    )


# ── 칸 쓰기 ─────────────────────────────────────────────

# 여러 규칙·서비스가 같이 쓰는 칸 경로
OCCUPATIONS_PATH = "/job_preferences/desired_occupations"
REGIONS_PATH = "/job_preferences/desired_regions"
GPA_SUFFIX = "/gpa"
GPA_SCALE_SUFFIX = "/gpa_scale"
CAREERS_STATUS = "/careers_status"
CERTIFICATIONS_STATUS = "/certifications_status"
COMPETENCIES_STATUS = "/competencies_status"


def said(path: str, value: Any, *, status: FieldStatus = FieldStatus.EXTRACTED) -> FieldWrite:
    """사용자가 말한(고른) 값 쓰기. 버튼으로 고른 값은 confirmed로 씁니다."""
    return FieldWrite(path=path, value=value, status=status, source=FieldSource.USER_ANSWER)


def chosen(path: str, value: Any) -> FieldWrite:
    return said(path, value, status=FieldStatus.CONFIRMED)


def not_applicable(path: str) -> FieldWrite:
    """섹션을 "없어요"로 저장합니다(예: 자격증 없음 → /certifications_status)."""
    return FieldWrite(path=path, status=FieldStatus.NOT_APPLICABLE, source=FieldSource.USER_ANSWER)


# ── 모델에 보여 줄 칸 목록 ───────────────────────────────

# 값 모양이 글자 하나가 아닌 칸. 읽기 모델이 이 모양으로 넣습니다.
VALUE_SHAPES: dict[str, str] = {
    "/job_preferences/desired_salary": (
        '{"amount": 원 단위 숫자, "unit": "monthly", "currency": "KRW", "negotiable": false}'
        " · 면접 후 결정이면 amount null, negotiable true"
    ),
    REGIONS_PATH: '["인천", "부천"] 지역 이름 목록(3곳까지)',
    "/competencies/computer_skills": '{"selected_skills": ["엑셀"], "other_skills": null}',
    "/competencies/languages": '["토익 800"] 글자 목록',
    "/additional_info/can_drive": "true | false",
    "/additional_info/owns_vehicle": "true | false",
}
# 모델이 경로로 직접 쓰지 않는 칸(반복 항목은 facts로, 상태 칸은 코드가 정함)
_NOT_WRITABLE = ("_status", "/item_id", "/occupation")


def writable_fields(data: Any) -> list[dict[str, Any]]:
    """지금 이력서의 칸 경로 전부와, 선택 칸이면 고를 값, 모양이 있는 칸이면 모양.

    읽기 모델이 "함께 말한 값"을 어느 칸에 넣을지 고를 때 씁니다. 경력·학력·자격증 항목을
    새로 만드는 것은 facts로 하므로 여기 없습니다.
    """
    from app.schemas.forms.resume import choices_of  # noqa: PLC0415 - 순환 import 피하기

    out: list[dict[str, Any]] = []
    for path, _ in form_fields(data):
        if path.endswith(_NOT_WRITABLE):
            continue
        entry: dict[str, Any] = {"path": path}
        if allowed := choices_of(path):
            entry["allowed"] = list(allowed)
        elif shape := VALUE_SHAPES.get(path):
            entry["shape"] = shape
        out.append(entry)
    return out
