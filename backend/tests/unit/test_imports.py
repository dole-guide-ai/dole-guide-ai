"""고용24 불러오기 항목을 서류·활동 값으로 바꾸는 규칙 (F-10)."""

from app.rules.imports import application_values, career_values, license_values


def test_career_reads_company_and_months() -> None:
    v = career_values("OO산업", "고용보험 상용 이력 · 2004.03 ~ 2026.09")

    assert (v.company_name, v.start_date, v.end_date) == ("OO산업", "2004-03", "2026-09")


def test_license_reads_issuer_and_date() -> None:
    v = license_values("지게차운전기능사", "한국산업인력공단 · 2011.05.20 취득")

    assert (v.issuing_organization, v.acquired_date) == ("한국산업인력공단", "2011-05-20")


def test_application_reads_company_job_and_result() -> None:
    v = application_values("OO물산 · 사무보조", "고용24 입사지원 · 서류전형 심사진행 중")

    assert (v.org_name, v.job_title, v.result) == ("OO물산", "사무보조", "서류전형 심사진행 중")
