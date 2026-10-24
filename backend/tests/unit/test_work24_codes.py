from app.schemas.forms.resume import OccupationStatus
from app.services.work24_codes import list_regions, load_codes, lookup_code, name_only


def test_codes_file_has_hierarchy() -> None:
    codes = load_codes()
    regions = {c.code: c for c in codes["region"]}
    assert all(c.parent in regions for c in codes["region"] if c.depth == 2)
    jobs = codes["occupation"]
    assert {c.depth for c in jobs} == {1, 2, 3}
    assert len(list_regions()) == len(codes["region"])


def test_lookup_returns_short_names_first_and_ignores_spaces() -> None:
    found = lookup_code("occupation", "지게차")
    assert [c.name for c in found][0] == "지게차 운전원"
    assert all(c.depth == 3 for c in found)
    assert lookup_code("occupation", "지게차운전원")[0].code == found[0].code
    assert len(lookup_code("occupation", "사무원")) == 3
    assert len(lookup_code("occupation", "사무원", limit=10)) == 10


def test_lookup_region_and_no_match() -> None:
    assert [(c.code, c.name) for c in lookup_code("region", "안성")] == [("41550", "경기 안성시")]
    assert lookup_code("occupation", "우주비행사") == []
    assert lookup_code("region", "  ") == []


def test_name_only() -> None:
    assert name_only(" 프레스 반장 ") == {
        "code": None,
        "name": "프레스 반장",
        "status": OccupationStatus.NAME_ONLY,
    }
