"""패널에서 고른 공통코드 칸(rules/resume/edits): 코드 확인·희망 직종 목록 고치기."""

import pytest

from app.rules.resume.edits import InvalidCodeError, code_edit, code_kind
from app.schemas.forms.resume import ResumeData

OCCUPATIONS = "/job_preferences/desired_occupations"
ELECTRIC = {
    "code": "834001",
    "name": "아파트 전기관리원",
    "status": "confirmed",
    "said": "시설관리",
}


def _data() -> ResumeData:
    return ResumeData.model_validate(
        {
            "job_preferences": {
                "desired_occupations": [
                    {
                        "item_id": "o1",
                        "occupation": {"value": ELECTRIC, "status": "confirmed"},
                        "experience_type": {"value": "경력", "status": "confirmed"},
                    },
                    {
                        "item_id": "o2",
                        "occupation": {
                            "value": {"code": None, "name": "경비", "status": "name_only"},
                            "status": "confirmed",
                        },
                    },
                ]
            }
        }
    )


def test_code_paths() -> None:
    assert code_kind(OCCUPATIONS) == "occupation"
    assert code_kind(f"{OCCUPATIONS}/o1/occupation") == "occupation"
    assert code_kind("/careers/c1/occupation") == "occupation"
    assert code_kind("/job_preferences/desired_regions") == "region"
    assert code_kind("/careers/c1/company_name") is None


def test_occupation_list_keeps_same_items_adds_new_and_removes_dropped() -> None:
    # 고른 목록: 그대로 둔 아파트 전기관리원 + 새 택배원. 경비(이름만)는 뺐습니다.
    edit = code_edit(_data(), OCCUPATIONS, [{"code": "834001"}, {"code": "624100"}])

    # 같은 코드는 경력여부와 함께 그대로 두고 쓰지 않습니다(말한 이름도 유지).
    assert edit.writes == [
        (
            f"{OCCUPATIONS}/o3/occupation",
            {"code": "624100", "name": "택배원", "status": "confirmed", "said": "택배원"},
        )
    ]
    assert edit.removed == [f"{OCCUPATIONS}/o2"]


def test_name_only_and_region_values_are_shaped_by_the_server() -> None:
    edit = code_edit(_data(), OCCUPATIONS, [{"code": "834001"}, {"name": "경비"}])
    assert edit.writes == [] and edit.removed == []

    regions = code_edit(_data(), "/job_preferences/desired_regions", [{"code": "11350"}])
    assert regions.writes == [
        (
            "/job_preferences/desired_regions",
            [
                {
                    "code": "11350",
                    "name": "서울 노원구",
                    "status": "confirmed",
                    "said": "서울 노원구",
                }
            ],
        )
    ]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (OCCUPATIONS, [{"code": "999999"}]),
        (OCCUPATIONS, {"code": "834001"}),
        ("/careers/c1/occupation", {"code": "01"}),  # 대분류는 이력서에서 고르지 않음
        ("/job_preferences/desired_regions", [{"name": " "}]),
    ],
)
def test_codes_not_in_the_table_are_rejected(path: str, value: object) -> None:
    with pytest.raises(InvalidCodeError):
        code_edit(_data(), path, value)


def test_old_values_without_status_get_the_server_status() -> None:
    from app.rules.resume.edits import with_code_status

    data = ResumeData.model_validate(
        {"job_preferences": {"desired_regions": {"value": [{"code": None, "name": "인천"}]}}}
    )
    assert with_code_status(data).job_preferences.desired_regions.value == [
        {"code": None, "name": "인천", "status": "needs_confirmation"}
    ]


def test_clearing_a_license_code_clears_its_name_and_picking_a_code_keeps_the_open_item() -> None:
    from app.rules.resume.edits import code_edit
    from app.schemas.forms.resume import ResumeData

    data = ResumeData()
    cleared = code_edit(data, "/certifications/q1/certificate_code", None)
    assert cleared.writes == [
        ("/certifications/q1/certificate_code", None),
        ("/certifications/q1/certificate_name", None),
    ]

    # 고르기 전이던 직종(코드 없음)에 같은 이름의 코드를 고르면 그 항목을 지키고 직종만 바꿉니다.
    said = {"code": None, "name": "택배원", "status": "needs_confirmation", "said": "택배원"}
    data = ResumeData.model_validate(
        {
            "job_preferences": {
                "desired_occupations": [
                    {
                        "item_id": "o1",
                        "occupation": {"value": said},
                        "experience_type": {"value": "경력", "status": "confirmed"},
                    }
                ]
            }
        }
    )
    edit = code_edit(data, "/job_preferences/desired_occupations", [{"code": "624100"}])
    assert edit.removed == []
    assert [p for p, _ in edit.writes] == ["/job_preferences/desired_occupations/o1/occupation"]


def test_switching_a_picked_occupation_to_name_only_keeps_the_item() -> None:
    from app.rules.resume.edits import code_edit
    from app.schemas.forms.resume import ResumeData

    picked = {"code": "624100", "name": "택배원", "status": "confirmed", "said": "택배"}
    data = ResumeData.model_validate(
        {
            "job_preferences": {
                "desired_occupations": [
                    {
                        "item_id": "o1",
                        "occupation": {"value": picked},
                        "experience_type": {"value": "경력", "status": "confirmed"},
                    }
                ]
            }
        }
    )

    edit = code_edit(data, "/job_preferences/desired_occupations", [{"name": "택배원"}])

    assert edit.removed == []
    assert [(p, v["status"]) for p, v in edit.writes] == [
        ("/job_preferences/desired_occupations/o1/occupation", "name_only")
    ]


def test_without_a_code_table_the_old_code_does_not_stay(monkeypatch) -> None:
    from app.rules.resume import codes, edits
    from app.schemas.forms.resume import ResumeData

    monkeypatch.setattr(codes, "has_codes", lambda kind: False)
    monkeypatch.setattr(edits, "has_codes", lambda kind: False)
    old = {"code": "5001320", "name": "정보처리기사", "status": "confirmed"}
    data = ResumeData.model_validate(
        {
            "certifications": [
                {
                    "item_id": "q1",
                    "certificate_name": {"value": "정보처리기사", "status": "confirmed"},
                    "certificate_code": {"value": old, "status": "confirmed"},
                }
            ]
        }
    )
    base = "/certifications/q1"

    # 이름을 글로 고치면 예전 코드를 비웁니다.
    assert codes.code_for_name(f"{base}/certificate_name", "정보보안기사", data) == [
        (f"{base}/certificate_code", None)
    ]
    # 화면에서 이름만 고르면 코드 칸도 이름만 적은 값으로 씁니다.
    written = dict(
        edits.code_edit(data, f"{base}/certificate_code", {"name": "정보보안기사"}).writes
    )
    assert written[f"{base}/certificate_code"]["status"] == "name_only"
    assert written[f"{base}/certificate_name"] == "정보보안기사"
