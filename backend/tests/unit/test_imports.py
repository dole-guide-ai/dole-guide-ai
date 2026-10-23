from datetime import date

from app.services.imports import _company, _item, _names

ANCHOR = date(2026, 10, 21)


def test_names_reads_plain_and_form_field_values() -> None:
    rows = [
        {"company_name": "OO빌딩"},
        {"company_name": {"value": "OO산업", "status": "confirmed"}},
        {"company_name": ""},
        {},
    ]

    assert _names(rows, "company_name") == {"OO빌딩", "OO산업"}


def test_company_takes_name_before_separator() -> None:
    assert _company("OO물산 · 사무보조") == "OO물산"
    assert _company("OO물산") == "OO물산"


def test_item_marks_recorded_by_name() -> None:
    raw = {"import_id": "cc_career_001", "category": "career", "title": "OO산업", "detail": "d"}

    assert _item(raw, ANCHOR, {"OO산업"}).is_recorded is True
    assert _item(raw, ANCHOR, set()).is_recorded is False


def test_item_uses_seed_flag_when_no_resume_field() -> None:
    raw = {
        "import_id": "cc_training_001",
        "category": "training",
        "title": "용접 기초 과정",
        "detail": "d",
        "is_recorded": True,
    }

    assert _item(raw, ANCHOR, None).is_recorded is True


def test_item_turns_date_offset_into_date() -> None:
    raw = {
        "import_id": "wa_003",
        "category": "job_search",
        "title": "OO물산 · 사무보조",
        "detail": "d",
        "date_offset": -8,
    }

    item = _item(raw, ANCHOR, set(), name="OO물산")

    assert item.values == {
        "category": "job_search",
        "title": "OO물산 · 사무보조",
        "detail": "d",
        "date": date(2026, 10, 13),
    }
