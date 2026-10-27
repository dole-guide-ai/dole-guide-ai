"""이력서 대화에서 채울 칸을 순서대로 고릅니다 (상세기획 2-1.3). LLM·DB 없음.

- 어떤 칸을 어떤 질문으로, 꼭 채워야 하는지는 스키마(`schemas/forms/resume.py`의 `asked`)가
  정합니다. 여기서는 빈 칸을 질문 단위로 묶어 단계를 만들고(`_field_steps`), 질문마다 선택지·
  버튼 답·코드 제안을 붙입니다(`QUESTION_SPEC`).
- 칸 하나가 아니라 업무 규칙에서 나오는 질문(첫 경력, 예전 이력서 이후 경력, 퇴사월 확인,
  그 전 경력, 미룬 칸 확인, 저장 확인)은 코드에 둡니다.
- 미루기: 모른다·나중에 하겠다고 한 칸(deferred)과 두 번 물은 칸은 건너뛰고, 꼭 채울 칸 중
  미룬 칸만 남으면 한 번 다시 묻습니다(deferred_review).
- 문구는 `data/templates/resume_questions.json`에 두고 여기서는 변수만 채웁니다.
"""

import json
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path
from string import Formatter
from typing import Any

from app.rules.resume.check import (
    education_done,
    is_college,
    latest_career,
    old_careers_pending,
    unpicked_regions,
)
from app.rules.resume.codes import NAMED_CODES, name_for_code
from app.rules.resume.dates import ym
from app.rules.resume.fields import (
    CAREERS_STATUS,
    CERTIFICATIONS_STATUS,
    COMPETENCIES_STATUS,
    as_list,
    chosen,
    form_fields,
    is_filled,
    needs_check,
    not_applicable,
    occupation_name,
)
from app.rules.resume.items import new_item_id
from app.rules.work24_codes import (
    CodeKind,
    code_done,
    code_settled,
    lookup_code,
    match_code,
    name_only,
    picked,
    said_name,
)
from app.schemas.common import FieldStatus
from app.schemas.forms.resume import (
    ContractType,
    EducationLevel,
    ExperienceType,
    GraduationStatus,
    MilitaryAlternative,
    ResumeData,
    asked_fields,
)
from app.schemas.imports import ImportKind
from app.schemas.resume import FieldWrite

TEMPLATES_JSON = (
    Path(__file__).resolve().parents[3] / "data" / "templates" / "resume_questions.json"
)
RECENT_CAREERS = 3  # 경력이 많으면 최근 3건만 하던 일을 묻습니다 (2-1.8)
# 하던 일·직종이 이 글자보다 길면 제목에 넣지 않고 직종·회사로 대신합니다.
TITLE_SUBJECT_MAX = 12
WON_PER_MANWON = 10_000

# 버튼은 코드가 바로 처리할 수 있는 답만 둡니다. 말로 답하는 길은 질문 카드의 직접 입력란이라
# "말로 할게요" 같은 버튼은 두지 않습니다.
# 코드가 계산한 제안을 받아들이는 답(버튼). 여러 칸을 묶어 제안할 때도 같은 답을 씁니다.
ACCEPT = "네, 좋아요"
VALUE_CONFIRM = "resume.value_confirm"
# 코드가 바꿔 적은 값(예: "2022년" → 2022년 3월)을 그대로 두는 버튼. 누르면 확정합니다.
CONFIRM_YES = "네, 맞아요"
# 미룬 칸만 남았을 때의 답
FILL_NOW = "지금 채울게요"
FILL_LATER = "오른쪽 이력서에서 할게요"
DEFERRED_REVIEW = "resume.deferred_review"
MILITARY_PATH = "/job_preferences/military_alternative"
MILITARY_NO = "아니요, 해당 없어요"
MILITARY_YES = "네, 해당돼요"
# 희망 직종·지역은 고용24 공통코드 후보(최대 3개)에서 고릅니다 (2-1.4). 후보가 없거나 다 아니면
# 말한 이름만 적고(name_only) 저장 후 고용24에서 고르라고 안내합니다.
OCCUPATION_PICK = "resume.wish_job_pick"
OCCUPATION_UNMATCHED = "resume.wish_job_unmatched"
REGION_PICK = "resume.wish_region_pick"
REGION_UNMATCHED = "resume.wish_region_unmatched"
NOT_IN_LIST = "목록에 없어요"
NAME_ONLY_ANSWER = "이름만 적을게요"
# 희망 직종 경력 합계 제안(질문 12)을 받지 않을 때. 말로 받은 값은 모델이 읽습니다.
EXPERIENCE_OTHER = "다르게 말할게요"
EXPERIENCE_FIELDS = ("experience_type", "experience_years", "experience_months")
_EXPERIENCE_PATH = re.compile(r"/desired_occupations/[^/]+/experience_")
SAVE_READY = "resume.save_ready"
# 꼭 채울 칸을 미룬 채 끝까지 왔을 때의 마지막 안내("다 채웠어요" 대신)
SAVE_AFTER_FILL = "resume.save_after_fill"
# "있어요"처럼 값 없이 다음 질문을 부르는 버튼 → 이어서 낼 질문(선택지 없이 말로 받음)
FOLLOW_UPS: dict[tuple[str, str], str] = {
    ("resume.license", "있어요"): "resume.license_name",
    ("resume.career_more", "네, 있어요"): "resume.career_prev",
    ("resume.career_end_check", "네, 있어요"): "resume.career_later",
    ("resume.optional_sections", "있어요"): "resume.optional_detail",
    # "대학교"만으로는 고용24 학력(2/3년제·4년제)을 정할 수 없어 종류를 한 번 더 묻습니다.
    ("resume.education_level", "대학교 졸업"): "resume.education_kind",
    ("resume.wish_military", MILITARY_YES): "resume.wish_military_kind",
}
# 이어지는 질문의 칸·파일 여부(저장은 읽기 모델의 facts로)
_FOLLOW_STEPS: dict[str, dict[str, Any]] = {
    "resume.license_name": {"paths": ("/certifications",), "accepts_file": True},
    "resume.career_prev": {
        "paths": ("/careers",),
        "accepts_file": True,
        "import_kind": ImportKind.CAREER_CERTIFICATE,
    },
    "resume.career_later": {
        "paths": ("/careers",),
        "accepts_file": True,
        "import_kind": ImportKind.CAREER_CERTIFICATE,
    },
    "resume.optional_detail": {"paths": ("/competencies",)},
    "resume.education_kind": {"paths": ("/education",), "spec": "education_kind"},
    "resume.wish_military_kind": {"paths": (MILITARY_PATH,), "spec": "wish_military_kind"},
}
CAREER_MORE = "resume.career_more"
CAREER_END_CHECK = "resume.career_end_check"
# 날짜를 몰라 그 칸을 미루는 답(버튼). 대화 노드가 미루기로 처리합니다.
DONT_KNOW = "기억이 안 나요"
# 같은 칸을 이만큼 물었는데도 비어 있으면(누가 물었든) 미룬 칸으로 보고 다음 칸으로 갑니다.
MAX_SAME_QUESTION = 2
# 면접 후 결정(금액 없음, 협의 가능)
NEGOTIABLE_SALARY = {"amount": None, "unit": "monthly", "currency": "KRW", "negotiable": True}


@dataclass(frozen=True)
class ResumeStep:
    """대화에서 채울 칸 하나(질문 하나). ID는 프론트 QUESTION_LABEL과 같습니다."""

    id: str
    vars: dict[str, Any] = field(default_factory=dict)
    choices: tuple[str, ...] = ()
    # 반복 항목(경력·학력·희망 직종) id. 미루기는 항목마다 따로 셉니다.
    item: str | None = None
    required: bool = True
    # 이 질문이 채우는 칸 경로. 새 항목이면 섹션 경로(`/careers`)
    paths: tuple[str, ...] = ()
    # 버튼 답 → 코드가 저장할 칸(빈 튜플이면 저장 없이 넘어감). 여기 없는 답은 모델이 처리합니다.
    answers: Mapping[str, tuple[FieldWrite, ...]] = field(default_factory=dict)
    # 코드가 계산한 제안(ACCEPT로 받아들이면 저장)과 그 근거
    proposal: tuple[FieldWrite, ...] = ()
    reason: str | None = None
    accepts_file: bool = False
    import_kind: ImportKind | None = None

    @property
    def key(self) -> str:
        return f"{self.id}:{self.item}" if self.item else self.id

    def answer_writes(self, answer: str) -> tuple[FieldWrite, ...] | None:
        """버튼 답이면 저장할 칸, 아니면 None(모델이 처리)."""
        if self.proposal and answer == ACCEPT:
            return self.proposal
        return self.answers.get(answer)

    def to_pending(self, text: str) -> dict[str, Any]:
        """질문을 낼 때 작업 기억(체크포인트)에 남길 정의. 답은 이것만 보고 처리합니다.

        진행표는 "다음에 뭘 물을까"라서 물은 횟수·미룸에 따라 바뀌지만, "방금 뭘 물었나"는
        바뀌면 안 됩니다. 그래서 질문의 정의를 통째로 저장합니다.
        """
        return {
            "id": self.id,
            "key": self.key,
            "text": text,
            "item": self.item,
            "paths": list(self.paths),
            "choices": list(self.choices),
            "answers": {
                c: [w.model_dump(mode="json") for w in ws] for c, ws in self.answers.items()
            },
            "proposal": [w.model_dump(mode="json") for w in self.proposal],
            "accepts_file": self.accepts_file,
            "import_kind": self.import_kind.value if self.import_kind else None,
        }

    @classmethod
    def from_pending(cls, pending: Mapping[str, Any]) -> ResumeStep:
        return cls(
            pending["id"],
            item=pending.get("item"),
            paths=tuple(pending.get("paths", [])),
            choices=tuple(pending.get("choices", [])),
            answers={
                c: tuple(FieldWrite.model_validate(w) for w in ws)
                for c, ws in pending.get("answers", {}).items()
            },
            proposal=tuple(FieldWrite.model_validate(w) for w in pending.get("proposal", [])),
            accepts_file=bool(pending.get("accepts_file", False)),
            import_kind=ImportKind(pending["import_kind"]) if pending.get("import_kind") else None,
        )


def _step(
    id_: str,
    *,
    proposal: tuple[FieldWrite, ...] = (),
    choices: tuple[str, ...] = (),
    **kw: Any,
) -> ResumeStep:
    if proposal and ACCEPT not in choices:
        choices = (ACCEPT, *choices)
    return ResumeStep(id_, proposal=proposal, choices=choices, **kw)


# ── 질문별 대화 정보(선택지·버튼 답·제안). 어떤 칸을 묻는지는 스키마가 정합니다 ─────


@dataclass(frozen=True)
class Spec:
    choices: tuple[str, ...] = ()
    answers: Mapping[str, tuple[FieldWrite, ...]] = field(default_factory=dict)
    proposal: tuple[FieldWrite, ...] = ()
    reason: str | None = None
    vars: dict[str, Any] = field(default_factory=dict)
    accepts_file: bool = False
    import_kind: ImportKind | None = None


# (이력서, 항목(없으면 None), 이 질문이 묻는 칸 경로들) → 대화 정보
SpecFn = Callable[[ResumeData, Any, tuple[str, ...]], Spec]


def _career_new(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    return Spec(
        choices=("사진 올릴게요", "고용24에서 불러올게요"),
        accepts_file=True,
        import_kind=ImportKind.CAREER_CERTIFICATE,
    )


def _career_period(data: ResumeData, c: Any, paths: tuple[str, ...]) -> Spec:
    return Spec(choices=(DONT_KNOW,), vars={"company": c.company_name.value})


def _career_position(data: ResumeData, c: Any, paths: tuple[str, ...]) -> Spec:
    return Spec(
        choices=("없었어요",),
        answers={"없었어요": (chosen(paths[0], "없음"),)},
        vars={"company": c.company_name.value},
    )


def _career_duties(data: ResumeData, c: Any, paths: tuple[str, ...]) -> Spec:
    return Spec(vars={"company": c.company_name.value})


def _education_level(data: ResumeData, e: Any, paths: tuple[str, ...]) -> Spec:
    base = paths[0].rsplit("/", 1)[0]
    return Spec(
        choices=("고등학교 졸업", "대학교 졸업"),
        answers={
            "고등학교 졸업": (
                chosen(f"{base}/education_level", EducationLevel.HIGH.value),
                chosen(f"{base}/graduation_status", GraduationStatus.GRADUATED.value),
            ),
            "대학교 졸업": (),  # 종류(2/3년제·4년제)를 이어 묻습니다(FOLLOW_UPS)
        },
    )


def _education_kind(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    """학력 종류(2/3년제·4년제)만 비었을 때. "대학교 졸업" 버튼 뒤나, 말로 "대학교"만 했을 때.

    새 항목이면 졸업도 같이 저장하고, 이미 있는 항목이면 학력만 채웁니다.
    """
    if item is not None:
        base = f"/education/{item.item_id}"
    else:
        base = f"/education/{new_item_id(data, 'education')}"
    extra = (
        ()
        if item is not None and is_filled(item.graduation_status)
        else (chosen(f"{base}/graduation_status", GraduationStatus.GRADUATED.value),)
    )
    kinds = (EducationLevel.COLLEGE, EducationLevel.UNIVERSITY)
    return Spec(
        choices=tuple(k.value for k in kinds),
        answers={k.value: (chosen(f"{base}/education_level", k.value), *extra) for k in kinds},
    )


def _education_school(data: ResumeData, e: Any, paths: tuple[str, ...]) -> Spec:
    return Spec(vars={"level": spoken_level(e.education_level.value)})


def _education_period(data: ResumeData, e: Any, paths: tuple[str, ...]) -> Spec:
    return Spec(choices=(DONT_KNOW,), vars={"level": spoken_level(e.education_level.value)})


def _license(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    return Spec(
        choices=("있어요", "없어요", "사진 올릴게요"),
        answers={"있어요": (), "없어요": (not_applicable(CERTIFICATIONS_STATUS),)},
        accepts_file=True,
    )


def _wish_job(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    latest = latest_career(data.careers)
    name = occupation_name(latest.occupation) if latest else None
    if not (latest and name):
        return Spec()
    return Spec(
        choices=("다른 일 할래요",),
        proposal=(chosen(paths[0], match_code("occupation", name)),),
        reason=f"{latest.company_name.value or '최근 회사'}에서 {name} 일을 하셨어요",
        vars={"occupation": name},
    )


def _wish_experience(data: ResumeData, d: Any, paths: tuple[str, ...]) -> Spec:
    return Spec(
        choices=("네, 맞아요", "아니요"),
        answers={
            "네, 맞아요": (chosen(paths[0], ExperienceType.EXPERIENCED.value),),
            "아니요": (chosen(paths[0], ExperienceType.NEW.value),),
        },
        vars={"occupation": occupation_name(d.occupation)},
    )


def _wish_wage(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    latest = latest_career(data.careers)
    salary = latest.monthly_salary.value if latest else None
    wage = salary // WON_PER_MANWON if isinstance(salary, int) and salary > 0 else None
    amount = {"amount": salary, "unit": "monthly", "currency": "KRW", "negotiable": False}
    return Spec(
        choices=("면접 후 결정할게요", "금액 말할게요"),
        answers={"면접 후 결정할게요": (chosen(paths[0], NEGOTIABLE_SALARY),)},
        proposal=(chosen(paths[0], amount),) if wage else (),
        reason=f"예전 직장 월급이 {wage}만 원이었어요" if wage else None,
        vars={"wage": wage} if wage else {},
    )


def _wish_employment(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    path = paths[0]
    return Spec(
        choices=("정해지지 않은 일", "정해진 일", "상관없어요"),
        answers={
            "정해지지 않은 일": (chosen(path, ContractType.PERMANENT.value),),
            "정해진 일": (chosen(path, ContractType.FIXED_TERM.value),),
            "상관없어요": (chosen(path, ContractType.ANY.value),),
        },
    )


def _wish_military(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    """병역대체 근무 희망. 부정을 다시 묻지 않고("해당이 없으시죠?") 찾는지를 바로 묻습니다.

    "해당돼요"면 종류를 이어서 묻습니다(FOLLOW_UPS → resume.wish_military_kind).
    """
    none = (chosen(paths[0], MilitaryAlternative.NONE.value),)
    return Spec(choices=(MILITARY_NO, MILITARY_YES), answers={MILITARY_NO: none, MILITARY_YES: ()})


def _wish_military_kind(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    kinds = [k.value for k in MilitaryAlternative if k != MilitaryAlternative.NONE]
    return Spec(
        choices=tuple(kinds),
        answers={k: (chosen(MILITARY_PATH, k),) for k in kinds},
    )


def _resume_title(data: ResumeData, item: Any, paths: tuple[str, ...]) -> Spec:
    title = suggest_resume_title(data)
    return Spec(
        choices=("다르게 할게요",), proposal=(chosen(paths[0], title),), vars={"title": title}
    )


QUESTION_SPEC: dict[str, SpecFn] = {
    "resume.career_new": _career_new,
    "resume.career_period": _career_period,
    "resume.career_position": _career_position,
    "resume.career_duties": _career_duties,
    "resume.education_level": _education_level,
    "resume.education_school": _education_school,
    "resume.education_period": _education_period,
    "resume.education_major": _education_school,
    "resume.education_gpa": lambda data, e, paths: Spec(
        choices=(DONT_KNOW,), vars={"level": spoken_level(e.education_level.value)}
    ),
    "resume.license": _license,
    "resume.wish_job": _wish_job,
    "resume.wish_experience": _wish_experience,
    "resume.wish_region": lambda data, item, paths: Spec(),
    "resume.wish_wage": _wish_wage,
    "resume.wish_employment": _wish_employment,
    "resume.wish_military": _wish_military,
    "resume.resume_title": _resume_title,
}


def spoken_level(level: Any) -> str | None:
    """선택지 값("대학교(4년제)")을 말로 쓰는 이름("대학교")으로. 질문 문장에 씁니다."""
    return re.sub(r"\(.*?\)", "", str(level)).strip() if level else None


def _field_steps(
    data: ResumeData, node: Any, base: str, item: Any = None, *, only: set[str] | None = None
) -> Iterator[ResumeStep]:
    """`node`의 빈 칸을 스키마의 질문 ID로 묶어 선언 순서대로 단계를 만듭니다.

    `only`: 이 질문들만(없으면 모두). 꼭 채울 칸(required)이 하나라도 든 질문은 required입니다.
    """
    grouped: dict[str, list[tuple[str, bool]]] = {}
    for name, question, required in asked_fields(type(node)):
        if only is not None and question not in only:
            continue
        if not is_filled(getattr(node, name)):
            grouped.setdefault(question, []).append((f"{base}/{name}", required))
    for question, fields in grouped.items():
        paths = tuple(path for path, _ in fields)
        spec = QUESTION_SPEC[question](data, item, paths)
        choices = spec.choices
        if spec.proposal and ACCEPT not in choices:
            choices = (ACCEPT, *choices)
        yield ResumeStep(
            question,
            vars=spec.vars,
            choices=choices,
            item=item.item_id if item is not None else None,
            required=any(required for _, required in fields),
            paths=paths,
            answers=spec.answers,
            proposal=spec.proposal,
            reason=spec.reason,
            accepts_file=spec.accepts_file,
            import_kind=spec.import_kind,
        )


# ── 순서 ────────────────────────────────────────────────

CAREER_FIELD_QUESTIONS = {"resume.career_period", "resume.career_position"}
COLLEGE_ONLY_QUESTIONS = {"resume.education_major", "resume.education_gpa"}


def _career_steps(
    data: ResumeData, entry_branch: str, separation_date: date, asked: Mapping[str, int] | None
) -> Iterator[ResumeStep]:
    careers = sorted(data.careers, key=lambda c: str(c.start_date.value or ""), reverse=True)
    if not careers and data.careers_status.status == FieldStatus.MISSING:
        spec = _career_new(data, None, ("/careers",))
        yield _step(
            "resume.career_new",
            choices=spec.choices,
            answers=spec.answers,
            paths=("/careers",),
            accepts_file=True,
            import_kind=spec.import_kind,
        )
        return
    if entry_branch == "E7b" and old_careers_pending(data):
        end = ym(careers[0].end_date.value) if careers else None
        yield _step(
            "resume.career_since_old",
            vars={"year": end[0] if end else None},
            choices=("네, 있어요", "없어요"),
            paths=("/careers", CAREERS_STATUS),
            answers={"없어요": (chosen(CAREERS_STATUS, "이후 경력 없음"),)},
        )
    for c in careers:
        # 근무 기간·직급은 스키마 선언 순서대로(기간이 고용24 필수 칸이라 먼저)
        yield from _field_steps(data, c, f"/careers/{c.item_id}", c, only=CAREER_FIELD_QUESTIONS)
    latest = latest_career(careers)
    separation = (separation_date.year, separation_date.month)
    # 마지막 경력의 퇴사월이 실업급여 기준 이직일과 다르면 "그 뒤 회사가 있는지" 한 번만 묻습니다.
    # 이직일은 계정(절차) 값이고 퇴사월은 사용자 말이라, 다르다고 퇴사월을 고치지 않습니다.
    end_key = f"{CAREER_END_CHECK}:{latest.item_id}" if latest else ""
    if (
        latest
        and ym(latest.end_date.value) != separation
        and latest.end_date.status != FieldStatus.CONFIRMED
        and not (asked or {}).get(end_key)
    ):
        end_path = f"/careers/{latest.item_id}/end_date"
        yield _step(
            CAREER_END_CHECK,
            vars={
                "company": latest.company_name.value,
                "year": separation[0],
                "month": separation[1],
            },
            item=latest.item_id,
            choices=("네, 있어요", "아니요, 마지막이에요"),
            paths=("/careers", end_path),
            # 마지막 회사면 적힌 퇴사월을 확정해 다시 묻지 않습니다. 있으면 그 회사를 말로 받습니다.
            answers={
                "네, 있어요": (),
                "아니요, 마지막이에요": (chosen(end_path, latest.end_date.value),),
            },
        )
    # 그 전 경력은 대화에서만 한 번 묻습니다(asked가 None이면 패널의 다음 질문이라 묻지 않음).
    if careers and asked is not None and not asked.get(CAREER_MORE):
        oldest = min(careers, key=lambda c: str(c.start_date.value or "9999"))
        yield _step(
            CAREER_MORE,
            vars={"company": oldest.company_name.value},
            required=False,
            choices=("네, 있어요", "없어요"),
            paths=("/careers",),
            answers={"네, 있어요": (), "없어요": ()},
        )


def _education_steps(data: ResumeData) -> Iterator[ResumeStep]:
    # 학교 이름·졸업은 말했는데 학력 종류만 비었으면(말로 "대학교"만 한 경우) 종류부터 묻습니다.
    for e in data.education:
        if not is_filled(e.education_level) and any(
            is_filled(f) for f in (e.school_name, e.graduation_status)
        ):
            spec = _education_kind(data, e, ())
            yield _step(
                "resume.education_kind",
                item=e.item_id,
                choices=spec.choices,
                answers=spec.answers,
                paths=(f"/education/{e.item_id}/education_level",),
            )
            return
    if not any(is_filled(e.education_level) for e in data.education):
        base = f"/education/{new_item_id(data, 'education')}"
        paths = (f"{base}/education_level", f"{base}/graduation_status")
        spec = _education_level(data, None, paths)
        yield _step(
            "resume.education_level", choices=spec.choices, paths=paths, answers=spec.answers
        )
        return
    for e in data.education:
        if education_done(e):
            continue
        # 전공·학점은 대학 이상만 묻습니다(스키마에서는 선택 칸, 대학 여부는 업무 규칙).
        college = is_college(e)
        for step in _field_steps(data, e, f"/education/{e.item_id}", e):
            if step.id in COLLEGE_ONLY_QUESTIONS and not college:
                continue
            yield step
        if college:
            yield from _named_code_picks(e, f"/education/{e.item_id}")


def _preference_steps(data: ResumeData) -> Iterator[ResumeStep]:
    prefs = data.job_preferences
    base = "/job_preferences"
    if not prefs.desired_occupations:
        path = f"{base}/desired_occupations/o1/occupation"
        spec = _wish_job(data, None, (path,))
        yield _step(
            "resume.wish_job",
            vars=spec.vars,
            choices=spec.choices,
            paths=(path,),
            proposal=spec.proposal,
            reason=spec.reason,
        )
    # 꼭 채울 칸 판정(check.occupation_done·unpicked_regions)과 같은 기준(code_done)으로
    # 공통코드를 고를 차례인 직종·지역을 묻습니다.
    for d in prefs.desired_occupations:
        item_base = f"{base}/desired_occupations/{d.item_id}"
        if not code_done(d.occupation.value):
            yield from _field_steps(data, d, item_base, d, only={"resume.wish_job"})
            if said := said_name(d.occupation.value):
                path = f"{item_base}/occupation"
                yield _code_pick("occupation", str(said), path, d.item_id, lambda v: v)
        yield from _experience_steps(data, d, item_base)
    regions = as_list(prefs.desired_regions)
    for region in unpicked_regions(prefs):
        i = regions.index(region)
        yield _code_pick(
            "region",
            str(said_name(region)),
            f"{base}/desired_regions",
            str(said_name(region)),
            lambda v, i=i: [*regions[:i], v, *regions[i + 1 :]],
        )
    yield from _field_steps(data, prefs, base)


def _experience_steps(data: ResumeData, d: Any, base: str) -> Iterator[ResumeStep]:
    """희망 직종 경력여부 (질문 12). 코드가 같은 직종 경력 합계를 제안했으면(derive_resume_values,
    확인 필요) "경력 9년 2개월로 적을까요?" 한 질문으로 확인받습니다. 세 칸을 따로 묻지 않습니다."""
    proposed = [n for n in EXPERIENCE_FIELDS if needs_check(getattr(d, n))]
    if not proposed:
        yield from _field_steps(data, d, base, d, only={"resume.wish_experience"})
        return
    paths = tuple(f"{base}/{n}" for n in proposed)
    spec = _wish_experience(data, d, (f"{base}/experience_type",))
    if not is_filled(d.experience_years):  # 경력이 없어 신입을 제안한 경우는 경력 여부를 묻습니다.
        yield _step(
            "resume.wish_experience",
            vars=spec.vars,
            item=d.item_id,
            choices=spec.choices,
            paths=paths,
            answers=spec.answers,
        )
        return
    years, months = d.experience_years.value, d.experience_months.value or 0
    evidence = d.experience_type.evidence
    yield _step(
        "resume.wish_experience",
        vars={**spec.vars, "years": years, "months": months},
        item=d.item_id,
        choices=(EXPERIENCE_OTHER,),
        paths=paths,
        proposal=tuple(chosen(f"{base}/{n}", getattr(d, n).value) for n in proposed),
        reason=evidence.note if evidence else None,
    )


_PICK_IDS: dict[CodeKind, tuple[str, str]] = {
    "occupation": (OCCUPATION_PICK, OCCUPATION_UNMATCHED),
    "region": (REGION_PICK, REGION_UNMATCHED),
    "license": ("resume.license_pick", "resume.license_unmatched"),
    "major": ("resume.major_pick", "resume.major_unmatched"),
}


def _named_code_picks(item: Any, base: str) -> Iterator[ResumeStep]:
    """이름은 있는데 코드를 아직 고르지 않은 자격면허·전공의 후보 고르기(짝: rules/resume/codes).
    꼭 채울 칸 판정(check.code_settled)과 같은 기준이라, 코드표가 없는 종류는 묻지 않습니다."""
    for name_field, (code_field, kind) in NAMED_CODES.items():
        if name_field not in type(item).model_fields:
            continue
        name, code = getattr(item, name_field), getattr(item, code_field)
        if is_filled(name) and not code_settled(kind, code.value):
            said = said_name(code.value) or str(name.value)
            yield _code_pick(kind, said, f"{base}/{code_field}", item.item_id, lambda v: v)


def _code_pick(
    kind: CodeKind, said: str, path: str, item: str, value: Callable[[Any], Any]
) -> ResumeStep:
    """말한 이름의 공통코드 후보(최대 3개)를 버튼으로. `value`는 고른 값 → 칸에 쓸 값."""
    candidates = lookup_code(kind, said)
    pick_id, unmatched_id = _PICK_IDS[kind]
    fallback = NOT_IN_LIST if candidates else NAME_ONLY_ANSWER

    def writes(code_value: dict[str, Any]) -> tuple[FieldWrite, ...]:
        # 자격면허·전공은 이름 칸도 공식 이름으로 같이 씁니다(rules/resume/codes).
        names = name_for_code(path, code_value) if code_value.get("code") else []
        return (chosen(path, value(code_value)), *(chosen(p, n) for p, n in names))

    answers = {c.name: writes(picked(c, said)) for c in candidates}
    answers[fallback] = writes(name_only(said))
    return _step(
        pick_id if candidates else unmatched_id,
        vars={"said": said},
        item=item,
        choices=tuple(answers),
        paths=(path,),
        answers=answers,
    )


def _shown(value: Any) -> str:
    """확인 질문에 보일 값. 연-월은 "2022년 3월"로 씁니다."""
    if parts := ym(value):
        return f"{parts[0]}년 {parts[1]}월"
    return str(value)


def _steps(
    data: ResumeData,
    *,
    entry_branch: str,
    separation_date: date,
    doc_failed: bool,
    skip_confirm: bool,
    asked: Mapping[str, int] | None,
) -> Iterator[ResumeStep]:
    if doc_failed:
        yield _step("resume.doc_retry", choices=("다시 찍을게요",), accepts_file=True)
    for path, f in form_fields(data):
        if not needs_check(f) or _EXPERIENCE_PATH.search(path):
            continue  # 경력 합계 제안은 희망 직종 경력 질문(_experience_steps)으로 확인받습니다.
        quote = f.evidence.quote if f.evidence else None
        if skip_confirm and not quote:
            continue  # 말에서 온 값이 아니면(서류끼리 다른 값 등) 패널에서 확인합니다.
        yield _step(
            VALUE_CONFIRM,
            vars={"path": path, "quote": quote, "value": _shown(f.value)},
            item=path,
            choices=(CONFIRM_YES,),
            paths=(path,),
            answers={CONFIRM_YES: (chosen(path, f.value),)},
        )
    yield from _career_steps(data, entry_branch, separation_date, asked)
    if not data.certifications and data.certifications_status.status == FieldStatus.MISSING:
        paths = ("/certifications", CERTIFICATIONS_STATUS)
        spec = _license(data, None, paths)
        yield _step(
            "resume.license",
            choices=spec.choices,
            paths=paths,
            answers=spec.answers,
            accepts_file=True,
        )
    for c in data.certifications:
        yield from _named_code_picks(c, f"/certifications/{c.item_id}")
    yield from _education_steps(data)
    yield from _preference_steps(data)
    yield from _field_steps(data, data, "", only={"resume.resume_title"})
    # 여기부터는 이력서를 더 좋게 하는 칸입니다(저장에 꼭 필요하지 않음).
    for c in sorted(data.careers, key=lambda c: str(c.start_date.value or ""), reverse=True)[
        :RECENT_CAREERS
    ]:
        yield from _field_steps(data, c, f"/careers/{c.item_id}", c, only={"resume.career_duties"})
    if data.competencies_status.status == FieldStatus.MISSING:
        yield _step(
            "resume.optional_sections",
            required=False,
            choices=("없어요", "있어요"),
            paths=("/competencies", COMPETENCIES_STATUS),
            answers={"있어요": (), "없어요": (not_applicable(COMPETENCIES_STATUS),)},
        )
    yield _step(SAVE_READY, required=False, choices=("확인하고 저장할게요", "고칠 게 있어요"))


def resume_steps(
    data: ResumeData,
    *,
    entry_branch: str,
    separation_date: date,
    doc_failed: bool = False,
    skip_confirm: bool = False,
    deferred: frozenset[str] = frozenset(),
    asked: Mapping[str, int] | None = None,
    follow: str | None = None,
) -> list[ResumeStep]:
    """남은 단계를 순서대로. 미룬 단계는 빼고, 꼭 채울 칸이 미룬 것만 남으면 미룬 칸 확인을
    앞에 둡니다. `follow`("있어요" 뒤에 이어 물을 질문 ID)가 있으면 그 질문을 맨 앞에 둡니다.

    `skip_confirm`: 대화에서는 말에서 온 값의 "바꾼 값 확인"만 묻습니다("네, 맞아요"를 누르면
    확정). 서류끼리 다른 값처럼 말로 답할 수 없는 확인은 패널의 "확인 필요" 표시로 합니다.
    """
    steps = list(
        _steps(
            data,
            entry_branch=entry_branch,
            separation_date=separation_date,
            doc_failed=doc_failed,
            skip_confirm=skip_confirm,
            asked=asked,
        )
    )
    # 두 번 물었는데도 비어 있는 칸은 미룬 칸으로 봅니다(누가 물었든 같은 질문을 되풀이하지 않음).
    capped = {k for k, n in (asked or {}).items() if n >= MAX_SAME_QUESTION}
    held_keys = deferred | capped
    left = [s for s in steps if s.key not in held_keys]
    if follow in _FOLLOW_STEPS:
        left.insert(0, _follow_step(data, follow))
    held = [s for s in steps if s.key in held_keys and s.required]
    if held and not any(s.required for s in left) and DEFERRED_REVIEW not in held_keys:
        left.insert(
            0,
            _step(
                DEFERRED_REVIEW,
                vars={"count": len(held)},
                required=False,
                choices=(FILL_NOW, FILL_LATER),
            ),
        )
    if held and left and left[-1].id == SAVE_READY:
        # 미룬 꼭 채울 칸이 남았으면 "다 채웠어요"라고 하지 않고 채운 뒤 저장하라고 안내합니다.
        left[-1] = _step(
            SAVE_AFTER_FILL, vars={"count": len(held)}, required=False, choices=(FILL_NOW,)
        )
    return left


def _follow_step(data: ResumeData, follow: str) -> ResumeStep:
    kw = dict(_FOLLOW_STEPS[follow])
    spec_name = kw.pop("spec", None)
    spec = _FOLLOW_SPEC[spec_name](data, None, kw["paths"]) if spec_name else Spec()
    return _step(follow, choices=spec.choices, answers=spec.answers, **kw)


_FOLLOW_SPEC: dict[str, SpecFn] = {
    "education_kind": _education_kind,
    "wish_military_kind": _wish_military_kind,
}


def next_resume_question(
    data: ResumeData,
    *,
    entry_branch: str,
    separation_date: date,
    doc_failed: bool = False,
    skip_confirm: bool = False,
) -> ResumeStep:
    """지금 물을 단계 하나(패널의 "AI가 물어볼 것"). 끝에는 늘 저장 확인이 있어 비지 않습니다."""
    return resume_steps(
        data,
        entry_branch=entry_branch,
        separation_date=separation_date,
        doc_failed=doc_failed,
        skip_confirm=skip_confirm,
    )[0]


# ── 제목 추천 ───────────────────────────────────────────


def suggest_resume_title(data: ResumeData) -> str:
    """경력으로 이력서 제목을 추천합니다(예: "물류 경력 이력서"). 경력이 없으면 희망 직종으로."""
    careers = sorted(data.careers, key=lambda c: str(c.start_date.value or ""), reverse=True)
    for c in careers:
        for subject in (occupation_name(c.occupation), c.main_duties.value, c.company_name.value):
            if subject and len(str(subject)) <= TITLE_SUBJECT_MAX:
                return f"{subject} 경력 이력서"
    for d in data.job_preferences.desired_occupations:
        if name := occupation_name(d.occupation):
            return f"{name} 희망 이력서"
    return "구직 이력서"


# ── 문구 ────────────────────────────────────────────────


@cache
def templates() -> dict[str, Any]:
    return json.loads(TEMPLATES_JSON.read_text(encoding="utf-8"))


def retry_text(step: ResumeStep, reasons: list[str]) -> str | None:
    """같은 질문을 다시 낼 때의 카드 문장: 저장하지 못한 이유 + 원래 질문.

    이유는 저장 규칙이 정한 문장(rules/resume/facts.FactPlan.reasons)을 그대로 씁니다. 모델이
    이유를 빠뜨리거나 질문을 한 번 더 쓰지 않게, 다시 묻는 카드는 코드가 만듭니다.
    """
    if (question := question_text(step)) is None:
        return None
    t = templates()["retry"]
    reason = " ".join(reasons) or t["unknown"]
    return t["text"].format(reason=reason, question=question)


def question_text(step: ResumeStep) -> str | None:
    """단계의 질문 문장. 문구가 없는 단계(예: 바꾼 값 확인)는 None이라 대화에서 묻지 않습니다.

    제안이 있으면 제안 문구를 씁니다. 문구 변수(회사 이름 등)가 비면 대명사("그곳")로 메우지 않고,
    이름 없이 쓴 문구(unnamed)나 변수별 설명 이름(fallbacks, 예: "최근에 다니신 회사")을 씁니다.
    """
    t = templates()
    template = (t["proposals"].get(step.id) if step.proposal else None) or t["questions"].get(
        step.id
    )
    if template is None:
        return None
    names = {name for _, name, _, _ in Formatter().parse(template) if name}
    values = {k: v for k, v in step.vars.items() if v not in (None, "")}
    missing = names - values.keys()
    if missing and step.id in t["unnamed"]:
        return t["unnamed"][step.id]
    return template.format(**{**{n: t["fallbacks"].get(n, "") for n in missing}, **values})
