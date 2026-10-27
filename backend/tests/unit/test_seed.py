"""시연 계정 seed가 이직일과 앞뒤가 맞는지 확인합니다 (DB 없음).

이직일은 입장일 기준 상대값이라, 어느 날 입장해도 마지막 경력의 퇴사월이 이직월과 같아야 합니다.
"""

from datetime import date

import pytest

from app.rules import imports as import_rules
from app.rules import resume as resume_rules
from app.services.accounts import seed_resume
from app.services.seed import at, read_seed_file, resolve_seed

PERSONAS = {p["persona_id"]: p for p in read_seed_file()}
ANCHORS = [date(2026, 10, 21), date(2026, 10, 27), date(2027, 2, 6)]


def _separation(seed: dict, anchor: date) -> date:
    return at(anchor, seed["procedure"]["separation_offset"])


def test_resolve_seed_fills_separation_month() -> None:
    seed = {
        "procedure": {"separation_offset": -21},
        "careers": [{"end_date": "{sep:%Y-%m}", "detail": "2004.03 ~ {sep:%Y.%m}"}],
        "quote": "그대로 둡니다",
    }

    resolved = resolve_seed(seed, date(2026, 10, 27))

    assert resolved["careers"] == [{"end_date": "2026-10", "detail": "2004.03 ~ 2026.10"}]
    assert resolved["quote"] == "그대로 둡니다"
    assert seed["careers"][0]["end_date"] == "{sep:%Y-%m}"  # 원본 seed는 바꾸지 않음


@pytest.mark.parametrize("anchor", ANCHORS, ids=str)
@pytest.mark.parametrize("persona_id", PERSONAS)
def test_latest_import_career_ends_in_separation_month(persona_id: str, anchor: date) -> None:
    seed = resolve_seed(PERSONAS[persona_id], anchor)
    separation = _separation(seed, anchor)
    careers = [
        import_rules.career_values(row["title"], row["detail"])
        for row in seed["imports"]["career_certificates"]
        if row["category"] == "career"
    ]
    if not careers:
        pytest.skip("불러올 경력이 없는 계정")

    assert max(c.end_date for c in careers) == f"{separation:%Y-%m}"


@pytest.mark.parametrize("persona_id", PERSONAS)
def test_import_list_has_only_items_that_can_be_applied(persona_id: str) -> None:
    """직업훈련은 불러오기로 넣지 못하므로(대화로 받음) 목록에 두지 않습니다."""
    rows = PERSONAS[persona_id]["imports"]["career_certificates"]

    assert all(row["category"] != "training" for row in rows)


@pytest.mark.parametrize("anchor", ANCHORS, ids=str)
def test_lee_resume_is_complete_and_matches_separation(anchor: date) -> None:
    """수급 중(4단계)인 이정호는 1단계 이력서 필수 칸이 모두 차 있고 이직일과 맞아야 합니다."""
    seed = resolve_seed(PERSONAS["lee"], anchor)
    separation = _separation(seed, anchor)
    data = seed_resume(seed["resume"]["data"], seed["resume"]["field_status"])

    assert resume_rules.can_save_resume(data)
    assert resume_rules.check_resume(data, separation, anchor) == []
    saved_on = at(anchor, seed["resume"]["saved_offset"])
    assert not resume_rules.saved_before_separation(saved_on, separation)


@pytest.mark.parametrize("anchor", ANCHORS, ids=str)
def test_choi_old_resume_is_older_than_new_career(anchor: date) -> None:
    """최영수의 예전 이력서는 이직 전에 저장했고, 그 뒤 경력은 불러오기에만 있습니다."""
    seed = resolve_seed(PERSONAS["choi"], anchor)
    saved_on = at(anchor, seed["resume"]["saved_offset"])
    old_end = max(c["end_date"] for c in seed["resume"]["data"]["careers"])

    assert resume_rules.saved_before_separation(saved_on, _separation(seed, anchor))
    assert f"{saved_on:%Y-%m}" > old_end
