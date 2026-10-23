"""첫 안내 문구 조립 (상세기획 1장 1.7). DB와 LLM을 쓰지 않는 순수 함수입니다.

조립 순서: 주 문구(분기 템플릿) → 현황 요약(E4b만) → 덧붙임(M1·M3) → 마지막 말풍선에 근거 한 줄.
문구는 `data/templates/entry.json`에 두고, 여기서는 상태 값으로 채우기만 합니다.
같은 상태면 늘 같은 문구라 테스트로 고정할 수 있습니다.
"""

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

TEMPLATES_JSON = Path(__file__).resolve().parents[2] / "data" / "templates" / "entry.json"
_WEEKDAYS = "월화수목금토일"
# 이직 당시 만 65세 이상이면 인터넷 사전제출 대신 센터 방문 (PROC-048, 덧붙임 M1)
ONLINE_PRESUBMIT_MAX_AGE = 65
M1_STAGES = ("job_registration", "education", "eligibility_application")
GENERAL_GROUP = "general"


@lru_cache(maxsize=1)
def templates() -> dict[str, Any]:
    return json.loads(TEMPLATES_JSON.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RoundFacts:
    """현황 요약(T-S)에 쓰는 이번 회차 점검 값 (`check_round` 결과)."""

    required: int | None
    required_job_search: int | None
    recorded: int
    counted: int
    counted_job_search: int
    weekly: bool = False


@dataclass(frozen=True)
class EntryFacts:
    """첫 안내를 채우는 상태 값. 이름은 가상 계정 표시 이름만 씁니다(개인정보 칸 아님)."""

    name: str
    stage: str
    rule_group: str
    age_at_separation: int
    round_no: int | None = None
    recognition_date: date | None = None
    d_day: int | None = None
    attendance: bool = False
    old_resume_year: int | None = None
    round_facts: RoundFacts | None = None


@dataclass(frozen=True)
class Composed:
    messages: list[tuple[str, str, str | None]]  # (template_id, text, cite)
    choices: list[str]
    rule_refs: list[str]
    accepts_file: bool


def korean_date(day: date) -> str:
    """12월 22일(화) (1.7 문구 원칙)."""
    return f"{day.month}월 {day.day}일({_WEEKDAYS[day.weekday()]})"


def short_date(day: date) -> str:
    """진행바 문구용 12.22(화)."""
    return f"{day.month:02d}.{day.day:02d}({_WEEKDAYS[day.weekday()]})"


def _cite(ids: list[str] | None) -> str | None:
    sources = templates()["sources"]
    return " / ".join(sources[i] for i in ids) if ids else None


def _summary(facts: EntryFacts) -> str | None:
    """T-S: 이번 회차 필요 활동과 지금 기록 상태."""
    rf, s = facts.round_facts, templates()["summary"]
    if rf is None or rf.required is None:
        return None
    values = {
        "round": facts.round_no,
        "required": rf.required,
        "required_job": rf.required_job_search,
        "recorded": rf.recorded,
        "counted": rf.counted,
        "remaining": max(rf.required - rf.counted, 0),
        "remaining_job": max((rf.required_job_search or 0) - rf.counted_job_search, 0),
    }
    parts = []
    if rf.weekly:
        parts.append(s["weekly"])
    else:
        need = s["required"] + (s["required_job"] if rf.required_job_search else s["required_end"])
        parts.append(need)
    parts.append(s["recorded_same_day"] if rf.counted < rf.recorded else s["recorded"])
    if values["remaining"]:
        parts.append(s["remaining"])
    elif values["remaining_job"]:
        parts.append(s["remaining_job"])
    else:
        parts.append(s["satisfied"])
    return " ".join(part.format(**values) for part in parts)


def compose(branch: str, facts: EntryFacts) -> Composed:
    """분기 하나의 첫 안내 말풍선·선택지·근거 규칙을 만듭니다. 말풍선은 최대 2개입니다."""
    t = templates()
    key = branch
    if branch == "E3":
        key = "E3a" if facts.attendance else "E3b"
    spec = t["branches"].get(key)
    if spec is None:
        return Composed([], [], [], False)
    values = {
        "name": facts.name,
        "round": facts.round_no,
        "completed": (facts.round_no or 1) - 1,
        "date": korean_date(facts.recognition_date) if facts.recognition_date else "",
        "d": facts.d_day,
        "old_resume_year": facts.old_resume_year or "",
        "age": facts.age_at_separation,
    }
    main = spec["text"].format(**values)
    refs = list(spec.get("rule_refs", []))
    cite_ids = list(spec.get("cite", []))
    if key == "E4a":
        group = "general" if facts.rule_group == GENERAL_GROUP else "other"
        main += " " + t["first_round_education"][group]
    if key == "E5a" and facts.age_at_separation < ONLINE_PRESUBMIT_MAX_AGE:
        main += " " + t["presubmit_online"]
    messages = [(f"T-{key}", main)]

    # 둘째 말풍선: 현황 요약(E4b) + 덧붙임(M3 출석 회차, M1 65세 이상 신청 경로)
    second: list[str] = []
    second_ids: list[str] = []
    if key == "E4b" and (summary := _summary(facts)):
        second.append(summary)
        second_ids.append("S")
        refs += t["summary"]["rule_refs"]
        cite_ids = t["summary"]["cite"]
    if facts.stage == "recognition" and facts.attendance and key in ("E4a", "E4b"):
        m3 = t["addons"]["M3"]
        second.append(m3["text"].format(**values))
        second_ids.append("M3")
        refs += m3["rule_refs"]
    if facts.age_at_separation >= ONLINE_PRESUBMIT_MAX_AGE and facts.stage in M1_STAGES:
        m1 = t["addons"]["M1"]
        second.append(m1["text"].format(**values))
        second_ids.append("M1")
        refs += m1["rule_refs"]
        cite_ids = cite_ids or m1["cite"]
    if second:
        messages.append(("T-" + "+".join(second_ids), " ".join(second)))

    # 근거 줄은 마지막 말풍선 아래에 한 줄 (1.7 조립 순서 4)
    cite = _cite(cite_ids)
    built = [
        (tid, text, cite if i == len(messages) - 1 else None)
        for i, (tid, text) in enumerate(messages)
    ]
    return Composed(
        messages=built,
        choices=list(spec["choices"]),
        rule_refs=list(dict.fromkeys(refs)),
        accepts_file=bool(spec.get("accepts_file", False)),
    )


def next_step_text(facts: EntryFacts) -> str:
    """진행바 위 다음 할 일 문구 (1.8 표)."""
    t = templates()["next_step"]
    m1 = facts.age_at_separation >= ONLINE_PRESUBMIT_MAX_AGE
    if facts.stage == "recognition":
        if not (facts.round_no and facts.recognition_date):
            return ""
        text = t["recognition"].format(
            round=facts.round_no, date=short_date(facts.recognition_date)
        )
        return text + (t["attendance"] if facts.attendance else "")
    if facts.stage in ("job_registration", "eligibility_application") and m1:
        return t[f"{facts.stage}_m1"]
    return t.get(facts.stage, "")


def stage_title(stage: str) -> str | None:
    return templates()["titles"].get(stage)
