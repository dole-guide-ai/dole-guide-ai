"""고용24 이력서 규칙 (상세기획 2-1). LLM·DB 없는 순수 함수입니다.

칸·선택지는 `schemas/forms/resume.py`가 정하고, 규칙은 모듈마다 하나씩 맡습니다.
- fields: 칸 하나의 상태(채움·확인 필요)와 칸 쓰기
- dates: 날짜 표현 → YYYY-MM
- items: 반복 항목 고르기(같은 회사·학교·자격증·직종은 같은 항목)
- facts: 모델이 뽑은 사실 → 칸 쓰기(날짜·선택지 맞추기)
- check: 자동 값·일관성 검사·완성도(꼭 묻는 5개)·꼭 넣을 칸·저장 가능 여부
- steps: 대화에서 채울 칸의 순서·선택지·코드 답·제안, 질문 문구

서비스는 `from app.rules import resume as rules`로 아래 이름을 씁니다.
"""

from app.rules.resume.check import (
    GPA_SCALE_ERROR,
    REQUIRED_SECTIONS,
    ResumeIssue,
    can_save_resume,
    check_resume,
    current_scale,
    derive_resume_values,
    gpa_scale_value,
    gpa_value,
    required_paths,
    resume_completeness,
    saved_before_separation,
    section_done,
)
from app.rules.resume.dates import DateResult, career_months, date_field, normalize_date
from app.rules.resume.fields import (
    form_fields,
    is_filled,
    needs_check,
    occupation_name,
    occupation_value,
)
from app.rules.resume.steps import (
    ResumeStep,
    next_resume_question,
    question_text,
    resume_steps,
    retry_text,
    suggest_resume_title,
)

__all__ = [
    "REQUIRED_SECTIONS",
    "DateResult",
    "ResumeIssue",
    "ResumeStep",
    "can_save_resume",
    "career_months",
    "check_resume",
    "current_scale",
    "date_field",
    "derive_resume_values",
    "form_fields",
    "GPA_SCALE_ERROR",
    "gpa_scale_value",
    "gpa_value",
    "is_filled",
    "needs_check",
    "next_resume_question",
    "normalize_date",
    "occupation_name",
    "occupation_value",
    "question_text",
    "required_paths",
    "resume_completeness",
    "resume_steps",
    "retry_text",
    "saved_before_separation",
    "section_done",
    "suggest_resume_title",
]
