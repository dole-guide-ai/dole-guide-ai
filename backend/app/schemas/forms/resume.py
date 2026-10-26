"""고용24 이력서 양식의 칸 구조입니다.

칸마다 값과 상태를 같이 두고(FormField), 경력·학력 같은 반복 항목은 item_id로 가리킵니다.
위치는 API·ERD 설계(`/careers/{item_id}/company_name`)를, 칸 이름은 데이터 설계 3장·4.2를 따릅니다.
꼭 묻는 항목은 제목, 학력, 희망조건, 경력, 자격면허 다섯 가지입니다.
"없어요"라고 답한 항목은 `*_status` 칸을 not_applicable로 두어 아직 안 물어본 것과 구분합니다.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import FormField

SCHEMA_VERSION = "work24_resume_v2"


class OccupationStatus(StrEnum):
    """직종 값의 공통코드 확정 상태 (상세기획 2-1.4)."""

    CONFIRMED = "confirmed"
    NEEDS_CONFIRMATION = "needs_confirmation"  # 후보를 아직 고르지 않음
    NAME_ONLY = "name_only"  # 세 번 안 맞아 말한 이름만 저장


class EducationLevel(StrEnum):
    NONE = "무학"
    ELEMENTARY = "초등학교"
    MIDDLE = "중학교"
    HIGH = "고등학교"
    COLLEGE = "대학교(2/3년제)"
    UNIVERSITY = "대학교(4년제)"
    MASTER = "대학원(석사)"
    DOCTOR = "대학원(박사)"


class GraduationStatus(StrEnum):
    LEAVE = "휴학"
    ENROLLED = "재학"
    DROPPED = "중퇴"
    COMPLETED = "수료"
    GRADUATED = "졸업"
    EXPECTED = "졸업예정"
    EXAM = "검정(독학)"


class ExperienceType(StrEnum):
    EXPERIENCED = "경력"
    NEW = "신입"


class EmploymentStatus(StrEnum):
    LEFT = "퇴직"
    EMPLOYED = "재직"


class ContractType(StrEnum):
    PERMANENT = "기간의 정함이 없는 근로계약"
    FIXED_TERM = "기간의 정함이 있는 근로계약"
    ANY = "관계없음"


class MilitaryAlternative(StrEnum):
    NONE = "해당 없음"
    ACTIVE = "현역병입영대상자"
    RESERVE = "보충역대상자"
    RESEARCH = "전문연구요원"
    INDUSTRIAL = "산업기능요원"


# 칸 이름 → 고를 수 있는 값(고용24 선택지). 저장 검증과 대화 진행표가 이 목록 하나를 씁니다.
CHOICE_FIELDS: dict[str, type[StrEnum]] = {
    "education_level": EducationLevel,
    "graduation_status": GraduationStatus,
    "experience_type": ExperienceType,
    "employment_status": EmploymentStatus,
    "employment_contract_type": ContractType,
    "military_alternative": MilitaryAlternative,
}


def choices_of(path: str) -> tuple[str, ...]:
    """칸 경로(`/education/e1/education_level`)의 선택지. 선택 칸이 아니면 빈 튜플."""
    enum = CHOICE_FIELDS.get(path.rsplit("/", 1)[-1])
    return tuple(e.value for e in enum) if enum else ()


# 칸 메타데이터 키(json_schema_extra): 어떤 질문이 이 칸을 묻는지, 꼭 채울 칸인지.
# JSON Schema 예약어(required 등)와 겹치면 OpenAPI 생성이 깨지므로 확장 키(x-)로 둡니다.
ASK = "x-ask"
REQUIRED = "x-required"


def asked(question: str, *, required: bool = True) -> Any:
    """대화에서 `question` 단계가 묻는 칸. 같은 question을 가진 칸은 한 질문으로 묶어 묻습니다.

    칸의 선언 순서가 묻는 순서입니다. 질문 문구는 `data/templates/resume_questions.json`,
    선택지·버튼 답·제안은 `rules/resume/steps.py`가 question ID로 붙입니다.
    """
    return Field(default=FormField(), json_schema_extra={ASK: question, REQUIRED: required})


def asked_fields(model: type[BaseModel]) -> list[tuple[str, str, bool]]:
    """모델의 (칸 이름, 질문 ID, 꼭 채울 칸인지)를 선언 순서대로."""
    out = []
    for name, info in model.model_fields.items():
        extra = info.json_schema_extra
        if isinstance(extra, dict) and ASK in extra:
            out.append((name, str(extra[ASK]), bool(extra.get(REQUIRED, True))))
    return out


def required_fields(model: type[BaseModel]) -> list[str]:
    return [name for name, _, required in asked_fields(model) if required]


class _Form(BaseModel):
    # 없는 칸 이름으로 쓰면 조용히 버려지지 않고 검증 오류가 나게 합니다.
    model_config = ConfigDict(extra="forbid")


class Education(_Form):
    item_id: str
    education_level: FormField = asked("resume.education_level")  # EducationLevel
    graduation_status: FormField = asked("resume.education_school")  # GraduationStatus
    school_name: FormField = asked("resume.education_school")
    start_date: FormField = asked("resume.education_period")  # YYYY-MM
    end_date: FormField = asked("resume.education_period")  # YYYY-MM
    gpa: FormField = asked("resume.education_gpa", required=False)  # 대학 이상만 묻는 선택 칸
    gpa_scale: FormField = asked("resume.education_gpa", required=False)
    major: FormField = asked("resume.education_major", required=False)  # 대학 이상만 필수
    double_major: FormField = FormField()
    minor: FormField = FormField()
    dual_major: FormField = FormField()
    is_highest_education: FormField = FormField()


class DesiredOccupation(_Form):
    item_id: str
    occupation: FormField = asked("resume.wish_job")  # {code, name, status: OccupationStatus}
    experience_type: FormField = asked("resume.wish_experience")  # ExperienceType
    experience_years: FormField = FormField()
    experience_months: FormField = FormField()
    desired_job_description: FormField = FormField()


class JobPreferences(_Form):
    desired_occupations: list[DesiredOccupation] = []
    desired_regions: FormField = asked("resume.wish_region")  # [{code, name}] 최대 3곳
    desired_salary: FormField = asked("resume.wish_wage")  # {amount, unit, currency, negotiable}
    employment_contract_type: FormField = asked("resume.wish_employment")  # ContractType
    work_arrangements: FormField = FormField()
    desired_working_hours: FormField = FormField()
    military_alternative: FormField = asked("resume.wish_military")  # MilitaryAlternative
    other_preferences: FormField = FormField()
    search_keywords: FormField = FormField()


class Career(_Form):
    item_id: str
    company_name: FormField = asked("resume.career_new")
    start_date: FormField = asked("resume.career_period")  # YYYY-MM
    end_date: FormField = asked("resume.career_period")  # YYYY-MM
    position: FormField = asked("resume.career_position")
    employment_status: FormField = FormField()  # EmploymentStatus
    occupation: FormField = FormField()  # {code, name, status}
    monthly_salary: FormField = FormField()
    main_duties: FormField = asked("resume.career_duties", required=False)
    additional_details: FormField = FormField()


class Certification(_Form):
    item_id: str
    certificate_name: FormField = asked("resume.license")
    issuing_organization: FormField = FormField()
    acquired_date: FormField = FormField()  # YYYY-MM-DD


class Competencies(_Form):
    """그 밖의 보유역량 8개. "있으면" 한 번만 묻고, 완성도에는 넣지 않습니다."""

    projects: FormField = FormField()
    activities_awards: FormField = FormField()
    vocational_training: FormField = FormField()
    computer_skills: FormField = FormField()  # {selected_skills, other_skills}
    languages: FormField = FormField()
    overseas_experiences: FormField = FormField()
    completed_courses: FormField = FormField()
    job_skills: FormField = FormField()


class AdditionalInfo(_Form):
    can_drive: FormField = FormField()
    owns_vehicle: FormField = FormField()


class ResumeData(_Form):
    resume_title: FormField = asked("resume.resume_title")
    education: list[Education] = []
    job_preferences: JobPreferences = JobPreferences()
    careers: list[Career] = []
    careers_status: FormField = FormField()  # 경력 "없어요"면 not_applicable
    certifications: list[Certification] = []
    certifications_status: FormField = FormField()  # 자격면허 "없어요"면 not_applicable
    other_certifications: FormField = FormField()
    competencies: Competencies = Competencies()
    competencies_status: FormField = FormField()  # 그 밖의 역량을 물었는지, "없어요"인지
    additional_info: AdditionalInfo = AdditionalInfo()
