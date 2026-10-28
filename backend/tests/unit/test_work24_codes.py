"""고용24 공통코드 맞추기(rules/work24_codes): 후보 찾기·바로 확정·칸 값 상태. 합성 말만 씁니다."""

from app.rules.work24_codes import (
    code_done,
    code_status,
    load_codes,
    lookup_code,
    match_code,
    name_only,
    said_name,
)
from app.schemas.forms.resume import CodeStatus
from app.services.work24_codes import list_regions


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
        "status": CodeStatus.NAME_ONLY,
        "said": "프레스 반장",
    }


def test_excluded_words_in_parentheses_do_not_match() -> None:
    # "건물 보수원 및 영선원(아파트 기계·전기 시설관리 제외)"는 시설관리 일이 아닙니다.
    names = [c.name for c in lookup_code("occupation", "시설관리", limit=20)]
    assert "건물 보수원 및 영선원(아파트 기계·전기 시설관리 제외)" not in names
    assert lookup_code("occupation", "영선원")[0].code == "702901"


def test_same_code_appears_once_and_words_are_tried_when_whole_text_misses() -> None:
    codes = [c.code for c in lookup_code("occupation", "사무원", limit=20)]
    assert len(codes) == len(set(codes))
    assert {c.name for c in lookup_code("occupation", "생산직 프레스")} >= {"프레스 금형 제조원"}


def test_exact_unique_name_is_confirmed_otherwise_pick() -> None:
    assert match_code("occupation", "택배원")["code"] == "624100"
    assert match_code("region", "노원구") == {
        "code": "11350",
        "name": "서울 노원구",
        "status": "confirmed",
        "said": "노원구",
    }
    # 이름이 같은 구가 여러 시·도에 있으면 고르게 합니다.
    assert match_code("region", "중구")["status"] == "needs_confirmation"
    assert match_code("occupation", "전기관리") == {
        "code": None,
        "name": "전기관리",
        "status": "needs_confirmation",
        "said": "전기관리",
    }


def test_done_means_picked_with_code_or_name_only() -> None:
    assert code_done(match_code("region", "노원구"))
    assert code_done(name_only("프레스 반장"))
    assert not code_done(match_code("occupation", "전기관리"))
    # 상태가 없던 예전 값은 코드 유무로 봅니다. 코드 없이 확정이라고 적힌 값은 끝나지 않은 것.
    assert code_status({"code": None, "name": "인천"}) == CodeStatus.NEEDS_CONFIRMATION
    assert not code_done({"code": None, "name": "일반 사무", "status": "confirmed"})
    assert said_name({"code": "026501", "name": "총무 및 일반 사무원", "said": "일반 사무"}) == (
        "일반 사무"
    )


def test_common_words_and_renamed_licenses_use_the_alias_list() -> None:
    # "시설관리"는 직종 이름에 없는 말이라 짝 목록의 공식 이름이 후보로 나옵니다.
    assert [c.name for c in lookup_code("occupation", "시설관리")] == [
        "아파트 전기관리원",
        "빌딩 전기관리원",
        "건물 관리원",
    ]
    assert match_code("occupation", "시설관리")["status"] == "needs_confirmation"
    # 이름이 바뀐 자격은 짝이 하나라 바로 확정합니다.
    renamed = match_code("license", "웹디자인기능사")
    assert (renamed["name"], renamed["status"], renamed["said"]) == (
        "웹디자인개발기능사",
        "confirmed",
        "웹디자인기능사",
    )


def test_region_can_stop_at_province_and_ignores_dong() -> None:
    # 시·군·구까지 꼭 고르지 않아도 됩니다. 시·도만 말하면 시·도 코드로 확정합니다.
    for said in ("서울", "서울시", "서울특별시"):
        assert match_code("region", said)["code"] == "11000"
    assert match_code("region", "경기도")["code"] == "41000"
    # 코드표는 시·군·구까지라 동은 떼고 찾습니다.
    assert match_code("region", "서울 노원구 상계동")["code"] == "11350"
    assert match_code("region", "부천시 심곡동")["name"] == "경기 부천시"
    # 구를 줄여 말한 "서울 강동"은 시·도로 확정하지 않고 고르게 합니다.
    assert match_code("region", "서울 강동")["status"] == "needs_confirmation"
    assert [c.name for c in lookup_code("region", "서울 강동")] == ["서울 강동구"]
    # 시·도 이름이 "구"로 끝나도(대구) 시·군·구로 보지 않아 동을 떼지 않습니다.
    assert match_code("region", "대구 남산동")["status"] == "needs_confirmation"
    assert match_code("region", "대구 중구 남산동")["name"] == "대구 중구"
    # 시·도 이름처럼 보여도 같은 이름의 시가 있으면 그 시입니다.
    assert match_code("region", "제주시")["name"] == "제주 제주시"


def test_region_code_for_search_skips_ambiguous_names() -> None:
    from app.rules.work24_codes import region_code

    assert region_code("서울").code == "11000"
    assert region_code("강남구").code == "11680"
    assert region_code("중구") is None  # 서울·부산·대구 … 여러 곳
    assert region_code("서울 중구").code == "11140"
