"""골든셋 '계정' 칸의 기본 상태값과 시작 데이터.

시연 계정 값은 backend/data/seeds/personas.json과 같습니다.

general·repeat·senior·park2처럼 시연 계정에 없는 경우는 가상 프리셋입니다. 모두 합성 값입니다.
"""

from copy import deepcopy
from typing import Any

BASE: dict[str, Any] = {
    "separation_date": "2026-08-31",
    "age_at_separation": 52,
    "has_disability": False,
    "recipient_type": "general",
    "employment_type": "regular",
    "stage": "job_registration",
    "resume_status": "none",
    "education_done": False,
    "eligibility_applied_date": None,
    "completed_rounds": 0,
    "last_recognition_date": None,
    "next_recognition_date": None,
    "demo_today": "2026-10-12",
    "demo_time": "10:00",
}
RECOGNITION = {"stage": "recognition", "resume_status": "ready", "education_done": True}
APPLIED = {**RECOGNITION, "eligibility_applied_date": "2026-09-15"}


def _round(done: int, last: str | None, nxt: str, today: str) -> dict[str, Any]:
    dates = {"last_recognition_date": last, "next_recognition_date": nxt, "demo_today": today}
    return {**APPLIED, "completed_rounds": done, **dates}


GENERAL = {
    1: _round(0, None, "2026-09-29", "2026-09-22"),
    2: _round(1, "2026-09-29", "2026-10-27", "2026-10-21"),
    3: _round(2, "2026-10-27", "2026-11-24", "2026-11-18"),
    4: _round(3, "2026-11-24", "2026-12-22", "2026-12-16"),
    # 5~7차는 지금 문항에 없어 비워 두고, 8차는 "7일마다 1건" 규칙(일반 8차부터)용입니다.
    5: _round(4, "2026-12-22", "2027-01-19", "2027-01-13"),
    8: _round(7, "2027-03-16", "2027-04-13", "2027-04-07"),
}
PARK = {"separation_date": "2026-09-30", "age_at_separation": 61}
CHOI = {"separation_date": "2026-09-30", "age_at_separation": 67, "resume_status": "outdated"}
LEE = {"age_at_separation": 58, **GENERAL[4]}

PERSONAS: dict[str, dict[str, Any]] = {
    "base": {},
    "park": PARK,
    "choi": CHOI,
    "lee": LEE,
    **{f"general{n}": GENERAL[n] for n in GENERAL},
    # 이력서는 끝났고 온라인 교육을 들어야 하는 단계
    "edu": {"stage": "education", "resume_status": "ready"},
    # 수급자격 신청서를 내고 1차 실업인정을 기다리는 단계
    "applied": {
        "stage": "eligibility_applied",
        "resume_status": "ready",
        "education_done": True,
        "eligibility_applied_date": "2026-09-15",
        "demo_today": "2026-09-18",
    },
    "repeat2": {**GENERAL[2], "recipient_type": "repeat"},
    "repeat3": {**GENERAL[3], "recipient_type": "repeat"},
    "repeat5": {**GENERAL[5], "recipient_type": "repeat"},
    "senior1": {**GENERAL[1], "age_at_separation": 67},
    "senior2": {**GENERAL[2], "age_at_separation": 67},
    "park2": {
        **PARK,
        **_round(1, "2026-11-10", "2026-12-08", "2026-12-01"),
        "eligibility_applied_date": "2026-10-20",
    },
}

LEE_ACTIVITIES = [
    {"date": "2026-12-08", "kind": "job_search", "route": "work24", "org_name": "OO물류"},
    {"date": "2026-12-08", "kind": "job_search", "route": "company_site", "org_name": "OO상사"},
]


def _career(company: str, start: str, end: str, duties: str | None = None) -> dict[str, Any]:
    return {
        "company_name": company,
        "start_date": start,
        "end_date": end,
        "position": None,
        "main_duties": duties,
        "monthly_salary": None,
    }


def empty_resume() -> dict[str, Any]:
    return {
        "education": [],
        "competencies": {"careers": [], "certifications": []},
        "job_preferences": {"desired_occupations": [], "desired_regions": []},
    }


# 상태값 칸의 seed=이름 으로 고르는 시작 이력서
# 상태값 칸에 BASE 밖에서 쓸 수 있는 이름. import_ids = 고용24 불러오기로 고른 항목(P-040)
EXTRA_STATE_KEYS = {"import_ids"}

SEEDS: dict[str, dict[str, Any]] = {
    "park_career": {
        "competencies": {
            "careers": [_career("OO산업", "2004-03", "2026-09")],
            "certifications": [{"certificate_name": "지게차운전기능사", "acquired_date": None}],
        }
    },
    # 경력·자격증·학력·희망 직종·지역은 찼고, 경력 여부·월급·고용형태·병역·제목은 남은 이력서
    "park_almost": {
        "competencies": {
            "careers": [
                {**_career("OO산업", "2004-03", "2026-09", "프레스 생산"), "position": "반장"}
            ],
            # 자격면허도 고용24 공통코드를 고른 값이어야 "찼다"로 봅니다(rules/resume/codes).
            "certifications": [
                {
                    "certificate_name": "지게차운전기능사",
                    "certificate_code": {
                        "code": "5007875",
                        "name": "지게차운전기능사",
                        "status": "confirmed",
                    },
                    "acquired_date": "2011-05-20",
                }
            ],
        },
        "education": [
            {
                "education_level": "고등학교",
                "graduation_status": "졸업",
                "school_name": "OO공업고등학교",
                "start_date": "1981-03",
                "end_date": "1984-02",
                "is_highest_education": True,
            }
        ],
        "job_preferences": {
            "desired_occupations": [
                {
                    "item_id": "occ_001",
                    "occupation": {
                        "code": "813207",
                        "name": "프레스기 및 절단기 조작원",
                        "status": "confirmed",
                    },
                }
            ],
            # 지역도 고용24 공통코드로 고른 값이어야 "찼다"로 봅니다(rules/work24_codes.code_done).
            "desired_regions": [{"code": "11620", "name": "서울 관악구", "status": "confirmed"}],
        },
    },
    "choi_resume_2019": {
        "competencies": {
            "careers": [_career("OO웹솔루션", "2005-03", "2019-04", "웹사이트 개발")],
            "certifications": [
                {
                    "certificate_name": "정보처리기사",
                    "certificate_code": {
                        "code": "5001320",
                        "name": "정보처리기사",
                        "status": "confirmed",
                    },
                    "acquired_date": "1998-11-15",
                }
            ],
        }
    },
}


def resolve_input(case_input: dict[str, Any]) -> dict[str, Any]:
    """계정 기본값 + 상태값 칸을 합쳐 완전한 상태와 시작 데이터를 만듭니다."""
    persona = case_input["persona"]
    if persona not in PERSONAS:
        raise ValueError(f"계정 '{persona}'을 모르겠어요. 쓸 수 있는 값: {', '.join(PERSONAS)}")
    overrides = dict(case_input["state"])
    seed = overrides.pop("seed", None)
    if seed is not None and seed not in SEEDS:
        raise ValueError(f"seed '{seed}'를 모르겠어요. 쓸 수 있는 값: {', '.join(SEEDS)}")
    allowed = [*BASE, *sorted(EXTRA_STATE_KEYS)]
    if unknown := [key for key in overrides if key not in allowed]:
        names = ", ".join(unknown)
        raise ValueError(
            f"상태값 이름 {names}을 모르겠어요(오타?). 쓸 수 있는 값: {', '.join(allowed)}"
        )
    state = {**BASE, **PERSONAS[persona], **overrides}
    # 시작 이력서(seed)를 줬는데 이력서 상태가 "없음"이면 러너가 seed를 버리므로 작성 중으로 봅니다.
    if seed and state["resume_status"] == "none":
        state["resume_status"] = "draft"
    resume = empty_resume()
    if seed:
        chosen = deepcopy(SEEDS[seed])
        resume["competencies"].update(chosen.pop("competencies"))
        resume.update(chosen)
    activities = case_input["activities"]
    if activities is None:
        activities = deepcopy(LEE_ACTIVITIES) if persona == "lee" else []
    data = {"resume": resume, "activities": activities, "recognition": {}}
    return {**case_input, "state": state, "activities": activities, "data": data}
