"""고용24 OpenAPI 응답 파싱과 스냅샷 대체 (F-29, 데이터 설계 8·9절). 실제 호출은 하지 않습니다."""

import xml.etree.ElementTree as ET
from datetime import date, datetime

from app.core.clock import KST
from app.schemas.trainings import ExternalSource
from app.services import trainings as training_service
from app.services import work24_api

TRAINING_XML = """<HRDNet><scn_cnt>1</scn_cnt><srchList><scn_list>
<trprId>T1</trprId><trprDegr>3</trprDegr><title>엑셀 실무</title><subTitle>OO학원</subTitle>
<traStartDate>20261109</traStartDate><traEndDate>20261218</traEndDate>
<address>서울 강남구</address><titleLink>https://example.test/t1</titleLink>
</scn_list></srchList></HRDNet>"""
PROGRAM_XML = """<empPgmSchdInviteList><total>1</total><empPgmSchdInvite>
<orgNm>OO고용센터</orgNm><pgmNm>이력서 특강</pgmNm><pgmSubNm>취업특강</pgmSubNm>
<pgmStdt>20261112</pgmStdt><pgmEndt>20261112</pgmEndt>
<openTimeClcd>2</openTimeClcd><openTime>2:00</openTime>
</empPgmSchdInvite></empPgmSchdInviteList>"""
NOW = datetime(2026, 10, 21, 9, tzinfo=KST)


def test_training_id_is_course_plus_degree() -> None:
    [t] = work24_api.parse_trainings(ET.fromstring(TRAINING_XML))

    assert (t.id, t.title, t.period) == ("T1:3", "엑셀 실무", "2026-11-09 ~ 2026-12-18")


def test_program_am_pm_code_and_no_made_up_id_or_url() -> None:
    [p] = work24_api.parse_programs(ET.fromstring(PROGRAM_XML))

    assert p.schedule == "2026-11-12 오후 2:00"
    assert (p.id, p.url) == (None, None)


def test_live_search_passes_keyword(monkeypatch) -> None:
    sent = {}

    def fake_get(url, params):
        sent.update(params)
        return ET.fromstring(TRAINING_XML)

    result = work24_api.fetch_trainings("사무", date(2026, 11, 1), date(2026, 11, 30), get=fake_get)

    assert (sent["srchTraProcessNm"], sent["srchTraStDt"], sent["srchTraEndDt"]) == (
        "사무",
        "20261101",
        "20261130",
    )
    assert result and result.items[0].id == "T1:3" and result.total == 1


def test_falls_back_to_snapshot_without_key(monkeypatch) -> None:
    """인증키가 없거나 호출이 실패하면 스냅샷으로 대체하고 source=snapshot입니다."""
    monkeypatch.setattr(work24_api, "fetch_trainings", lambda *a, **k: None)

    result = training_service.search_trainings("사무", None, NOW.date(), NOW)

    assert result.source == ExternalSource.SNAPSHOT
    assert result.items and all("사무" in t.title or "회계" in t.title for t in result.items)


def test_snapshot_applies_range_and_page(monkeypatch) -> None:
    monkeypatch.setattr(work24_api, "fetch_programs", lambda *a, **k: None)

    everything = training_service.search_programs(None, NOW)
    later = training_service.search_programs(date(2026, 11, 13), NOW)
    second_page = training_service.search_programs(None, NOW, page=2)

    assert later.total < everything.total
    assert all(p.schedule[:10] >= "2026-11-13" for p in later.items)
    assert second_page.items == [] and second_page.total == everything.total


def test_each_api_uses_its_own_key(monkeypatch) -> None:
    """고용24 인증키는 API마다 달라서, 호출마다 그 API의 키를 씁니다."""
    settings = work24_api.get_settings()
    monkeypatch.setattr(settings, "work24_training_api_key", "training-key")
    monkeypatch.setattr(settings, "work24_program_api_key", "program-key")

    assert work24_api._api_key(work24_api.TRAINING_URL) == "training-key"
    assert work24_api._api_key(work24_api.PROGRAM_URL) == "program-key"
