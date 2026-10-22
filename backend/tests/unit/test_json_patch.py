import pytest

from app.core.errors import UnprocessableError
from app.core.json_patch import apply_patch, split_status
from app.schemas.common import ErrorCode, FieldSource, FormName, JsonPatchOp


def field(value=None, status="missing"):
    return {
        "value": value,
        "status": status,
        "source": None,
        "transformed": False,
        "evidence": None,
        "answered_on": None,
    }


DATA = {
    "title": field(),
    "careers": [{"item_id": "c1", "company_name": field("OO물산", "extracted")}],
    "job_preferences": {},
}


def patch(*ops):
    return [JsonPatchOp(**op) for op in ops]


def run(*ops):
    return apply_patch(DATA, patch(*ops), form=FormName.RESUME, source=FieldSource.DIRECT)


def test_replace_field_confirms_value() -> None:
    data, updates = run({"op": "replace", "path": "/careers/c1/company_name", "value": "OO상사"})

    assert data["careers"][0]["company_name"]["value"] == "OO상사"
    assert data["careers"][0]["company_name"]["status"] == "confirmed"
    assert data["careers"][0]["company_name"]["source"] == "direct"
    assert updates[0].path == "/careers/c1/company_name"
    assert DATA["careers"][0]["company_name"]["value"] == "OO물산"  # 원본은 그대로


def test_add_new_key_in_dict() -> None:
    data, _ = run({"op": "add", "path": "/job_preferences/region", "value": "서울"})

    assert data["job_preferences"]["region"]["value"] == "서울"


def test_add_item_to_list_gets_item_id() -> None:
    data, updates = run({"op": "add", "path": "/careers/-", "value": {"company_name": "새회사"}})

    new = data["careers"][1]
    assert new["company_name"]["value"] == "새회사"
    assert updates[0].path == f"/careers/{new['item_id']}"


def test_remove_item_and_field() -> None:
    data, _ = run({"op": "remove", "path": "/careers/c1"})
    assert data["careers"] == []

    data, _ = run({"op": "remove", "path": "/title"})
    assert data["title"]["status"] == "missing"


@pytest.mark.parametrize("path", ["/nothing/here", "/careers/c9/company_name", "/careers", "/"])
def test_unknown_path_is_422_and_changes_nothing(path: str) -> None:
    with pytest.raises(UnprocessableError):
        run(
            {"op": "replace", "path": "/title", "value": "a"},
            {"op": "replace", "path": path, "value": 1},
        )


def test_status_cannot_mix_with_fields() -> None:
    only = patch({"op": "replace", "path": "/status", "value": "saved"})
    assert split_status(only) is only[0]
    assert split_status(patch({"op": "replace", "path": "/title", "value": "a"})) is None

    with pytest.raises(UnprocessableError) as exc:
        split_status(only + patch({"op": "replace", "path": "/title", "value": "a"}))
    assert exc.value.code == ErrorCode.STATUS_WITH_FIELDS
