"""고용24 이력서 양식의 칸 구조입니다.

칸마다 값과 상태를 같이 두고(FormField), 경력·학력 같은 반복 항목은 item_id로 가리킵니다.
위치는 API·ERD 설계(`/careers/{item_id}/company_name`)를, 칸 이름은 데이터 설계 3장·4.2를 따릅니다.
꼭 묻는 항목은 제목, 학력, 희망조건, 경력, 자격면허 다섯 가지입니다.
"없어요"라고 답한 항목은 `*_status` 칸을 not_applicable로 두어 아직 안 물어본 것과 구분합니다.
"""

from pydantic import BaseModel, ConfigDict

from app.schemas.common import FormField

SCHEMA_VERSION = "work24_resume_v2"


class _Form(BaseModel):
    # 없는 칸 이름으로 쓰면 조용히 버려지지 않고 검증 오류가 나게 합니다.
    model_config = ConfigDict(extra="forbid")


class Education(_Form):
    item_id: str
    education_level: FormField = FormField()  # 무학 ~ 대학원(박사) 8종
    graduation_status: FormField = FormField()  # 휴학·재학·중퇴·수료·졸업·졸업예정·검정(독학)
    school_name: FormField = FormField()
    start_date: FormField = FormField()  # YYYY-MM
    end_date: FormField = FormField()  # YYYY-MM
    gpa: FormField = FormField()
    gpa_scale: FormField = FormField()
    major: FormField = FormField()
    double_major: FormField = FormField()
    minor: FormField = FormField()
    dual_major: FormField = FormField()
    is_highest_education: FormField = FormField()


class DesiredOccupation(_Form):
    item_id: str
    occupation: FormField = (
        FormField()
    )  # {code, name, status: confirmed·needs_confirmation·name_only}
    experience_type: FormField = FormField()  # 신입 / 경력
    experience_years: FormField = FormField()
    experience_months: FormField = FormField()
    desired_job_description: FormField = FormField()


class JobPreferences(_Form):
    desired_occupations: list[DesiredOccupation] = []
    desired_regions: FormField = FormField()  # [{code, name}] 최대 3곳
    desired_salary: FormField = FormField()  # {amount, unit, currency, negotiable}
    employment_contract_type: FormField = FormField()
    work_arrangements: FormField = FormField()
    desired_working_hours: FormField = FormField()
    military_alternative: FormField = FormField()
    other_preferences: FormField = FormField()
    search_keywords: FormField = FormField()


class Career(_Form):
    item_id: str
    company_name: FormField = FormField()
    start_date: FormField = FormField()  # YYYY-MM
    end_date: FormField = FormField()  # YYYY-MM
    position: FormField = FormField()
    employment_status: FormField = FormField()  # 퇴직 / 재직
    occupation: FormField = FormField()  # {code, name, status}
    monthly_salary: FormField = FormField()
    main_duties: FormField = FormField()
    additional_details: FormField = FormField()


class Certification(_Form):
    item_id: str
    certificate_name: FormField = FormField()
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
    resume_title: FormField = FormField()
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
