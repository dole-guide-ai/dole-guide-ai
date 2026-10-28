"""고용24 불러오기 항목을 서류·활동 값으로 바꾸는 순수 함수입니다. DB와 HTTP를 모릅니다.

모의 목록의 제목·설명은 고용24 화면 문구 모양을 따릅니다.
- 경력: "고용보험 상용 이력 · 2004.03 ~ 2026.09" → 시작·끝 연월
- 자격: "한국산업인력공단 · 2011.05.20 취득" → 발급기관·취득일
- 입사지원: 제목 "OO물산 · 사무보조" → 회사·모집 직종,
  설명 "고용24 입사지원 · 서류전형 심사진행 중" → 활동 결과
"""

import re
from dataclasses import dataclass

from app.schemas.imports import ImportCategory

SEPARATOR = " · "
# 경력·자격 항목이 들어가는 이력서 섹션. 같은 항목인지는 제목(회사·자격증 이름)으로 가릅니다.
RESUME_SECTIONS = {ImportCategory.CAREER: "careers", ImportCategory.LICENSE: "certifications"}
# 연월만 뽑습니다. 일까지 있으면(2004.03.15) 일은 버립니다.
_YM = re.compile(r"(\d{4})\.(\d{1,2})(?:\.\d{1,2})?(?!\d)")
_YMD = re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})")


@dataclass(frozen=True)
class CareerValues:
    company_name: str
    start_date: str | None
    end_date: str | None


@dataclass(frozen=True)
class LicenseValues:
    certificate_name: str
    issuing_organization: str | None
    acquired_date: str | None


@dataclass(frozen=True)
class ApplicationValues:
    org_name: str
    job_title: str | None
    result: str | None


def _parts(text: str) -> list[str]:
    return [part.strip() for part in text.split(SEPARATOR)]


def resume_target(category: str, title: str) -> tuple[str, str] | None:
    """(이력서 섹션, 같은 항목을 가르는 이름). 이력서에 들어가지 않는 범주면 None."""
    section = RESUME_SECTIONS.get(ImportCategory(category))
    return (section, title.strip()) if section else None


def career_values(title: str, detail: str) -> CareerValues:
    months = [f"{y}-{int(m):02d}" for y, m in _YM.findall(detail)]
    return CareerValues(
        company_name=title.strip(),
        start_date=months[0] if months else None,
        end_date=months[1] if len(months) > 1 else None,
    )


def license_values(title: str, detail: str) -> LicenseValues:
    parts = _parts(detail)
    day = _YMD.search(detail)
    return LicenseValues(
        certificate_name=title.strip(),
        issuing_organization=parts[0] if len(parts) > 1 else None,
        acquired_date=f"{day[1]}-{int(day[2]):02d}-{int(day[3]):02d}" if day else None,
    )


def application_values(title: str, detail: str) -> ApplicationValues:
    org, *job = _parts(title)
    detail_parts = _parts(detail)
    return ApplicationValues(
        org_name=org,
        job_title=job[0] if job else None,
        result=detail_parts[1] if len(detail_parts) > 1 else None,
    )
