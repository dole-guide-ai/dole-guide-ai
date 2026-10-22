"""고용24 이력서 양식의 칸 구조입니다.

칸마다 값과 상태를 같이 두고(FormField), 경력·학력 같은 반복 항목은 item_id로 가리킵니다.
꼭 묻는 항목은 제목, 학력, 희망조건, 경력, 자격면허 다섯 가지입니다.
"""

from typing import Any

from pydantic import BaseModel

from app.schemas.common import FormField

SCHEMA_VERSION = "work24_resume_v2"


class ResumeData(BaseModel):
    title: FormField = FormField()
    education: list[dict[str, Any]] = []
    job_preferences: dict[str, Any] = {}
    careers: list[dict[str, Any]] = []
    certifications: list[dict[str, Any]] = []
    # 그 밖의 역량 8개(직무능력·컴퓨터 활용 등). "있으면" 한 번만 묻습니다.
    competencies: dict[str, Any] = {}
