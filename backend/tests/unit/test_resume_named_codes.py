"""자격면허·전공의 공통코드(rules/resume/codes): 코드표가 있으면 직종처럼 고르고, 없으면 묻지 않음.

코드표는 인증키로 받아야 해서, 여기서는 합성 코드표를 끼워 넣어 같은 규칙이 도는지 봅니다.
"""

from datetime import date

import pytest

from app.rules import work24_codes
from app.rules.resume import resume_steps, section_done
from app.rules.resume.edits import code_edit
from app.rules.resume.facts import CertificationFact, ResumeFacts, plan_writes
from app.schemas.codes import CodeRead
from app.schemas.forms.resume import ResumeData

TODAY = date(2026, 10, 21)
SEPARATION = date(2026, 9, 30)
LICENSES = (
    CodeRead(code="L1", name="국가기술자격", parent=None, depth=1),
    CodeRead(code="1320", name="정보처리기사", parent="L1", depth=2),
    CodeRead(code="1321", name="정보처리산업기사", parent="L1", depth=2),
)


def _use_licenses(monkeypatch: pytest.MonkeyPatch, licenses: tuple[CodeRead, ...]):
    real = work24_codes.load_codes()
    monkeypatch.setattr(work24_codes, "load_codes", lambda: {**real, "license": licenses})
    work24_codes._choosable.cache_clear()
    work24_codes._by_id.cache_clear()
    yield
    work24_codes._choosable.cache_clear()
    work24_codes._by_id.cache_clear()


@pytest.fixture
def with_licenses(monkeypatch: pytest.MonkeyPatch):
    """합성 자격면허 코드표(결과를 고정하려고 실제 3천여 건 대신)."""
    yield from _use_licenses(monkeypatch, LICENSES)


@pytest.fixture
def without_licenses(monkeypatch: pytest.MonkeyPatch):
    """자격면허 코드표를 받기 전 상태."""
    yield from _use_licenses(monkeypatch, ())


def _cert(code: dict | None) -> ResumeData:
    item = {"item_id": "q1", "certificate_name": {"value": "정보처리", "status": "extracted"}}
    if code:
        item["certificate_code"] = {"value": code, "status": "extracted"}
    return ResumeData.model_validate({"certifications": [item]})


def _steps(data: ResumeData) -> list:
    return resume_steps(data, entry_branch="E7a", separation_date=SEPARATION, asked={})


def test_without_a_code_table_certificates_are_not_held_back(without_licenses) -> None:
    assert not work24_codes.has_codes("license")
    data = _cert(None)
    assert section_done(data)["certifications"]
    assert "resume.license_pick" not in [s.id for s in _steps(data)]


def test_said_certificate_gets_a_code_or_a_pick(with_licenses) -> None:
    exact = plan_writes(
        ResumeData(),
        ResumeFacts(certifications=[CertificationFact(certificate_name="정보처리기사")]),
        TODAY,
        SEPARATION,
    )
    code = {w.path: w.value for w in exact.writes}["/certifications/q1/certificate_code"]
    assert (code["code"], code["status"]) == ("1320", "confirmed")

    data = _cert(work24_codes.match_code("license", "정보처리"))
    assert not section_done(data)["certifications"]  # 고르기 전이라 덜 참
    pick = next(s for s in _steps(data) if s.id == "resume.license_pick")
    assert pick.choices == ("정보처리기사", "정보처리산업기사", "목록에 없어요")
    # 고르면 코드 칸과 이름 칸(공식 이름)을 같이 씁니다.
    written = {w.path: w.value for w in pick.answer_writes("정보처리산업기사")}
    assert written["/certifications/q1/certificate_name"] == "정보처리산업기사"
    assert written["/certifications/q1/certificate_code"]["code"] == "1321"
    # 목록에 없으면 이름만 남기고(고용24 기타자격) 끝난 것으로 봅니다.
    other = {w.path: w.value for w in pick.answer_writes("목록에 없어요")}
    assert other == {"/certifications/q1/certificate_code": work24_codes.name_only("정보처리")}


def test_direct_pick_writes_code_and_official_name(with_licenses) -> None:
    edit = code_edit(_cert(None), "/certifications/q1/certificate_code", {"code": "1320"})
    assert dict(edit.writes)["/certifications/q1/certificate_name"] == "정보처리기사"
    # 분류(1단계)는 고를 수 없는 코드입니다.
    with pytest.raises(ValueError):
        code_edit(_cert(None), "/certifications/q1/certificate_code", {"code": "L1"})
