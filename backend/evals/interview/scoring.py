"""이력서 인터뷰 채점. LLM 없이 결과 이력서(골든셋 경로 모양)와 대화 기록만 봅니다.

- 칸 점수: 시나리오 사실마다 맞게 채웠는지(맞음 / 틀림 / 비어 있음).
  틀림은 지어내거나 칸을 헷갈린 것.
- 대화 지표: 에이전트가 물은 비율(주도성), 같은 질문 반복, 쓴 턴 수.
- 직종(career.occupation)은 한쪽 설계에 칸이 없어 본 점수에서 빼고 따로 셉니다.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from evals.interview.scenarios import Scenario

CORRECT, WRONG, MISSING = "맞음", "틀림", "비어 있음"
# 같은 질문으로 보는 글자 겹침 비율
REPEAT_OVERLAP = 0.8


@dataclass
class Score:
    fields: dict[str, str] = field(default_factory=dict)  # 칸 이름 → 결과
    occupation: dict[str, str] = field(default_factory=dict)
    extra_careers: int = 0  # 사실에 없는 회사로 만든 경력(지어냄)
    turns: int = 0
    asked: int = 0  # 질문으로 끝난 에이전트 답 수
    repeated: int = 0
    ended: bool = False  # 사용자가 [끝]으로 끝냄(더 물을 게 없다고 안내받음)

    @property
    def correct(self) -> int:
        return sum(v == CORRECT for v in self.fields.values())

    @property
    def wrong(self) -> int:
        return sum(v == WRONG for v in self.fields.values())

    @property
    def total(self) -> int:
        return len(self.fields)


def _text(value: Any) -> str:
    """칸 값 → 비교용 글자. 직종처럼 {name: ...}이면 이름."""
    if isinstance(value, dict):
        value = value.get("name") or value.get("value")
    if isinstance(value, list):
        return " ".join(_text(v) for v in value)
    return "" if value is None else str(value)


def _norm(text: str) -> str:
    return re.sub(r"[\s()（）㈜]|주식회사", "", text)


def _has(value: Any, *keys: str) -> bool:
    got = _norm(_text(value))
    return bool(got) and any(_norm(k) in got for k in keys)


def _judge(value: Any, ok: bool) -> str:
    return CORRECT if ok else (MISSING if not _norm(_text(value)) else WRONG)


def _ym(value: Any) -> str:
    m = re.match(r"(\d{4})-(\d{2})", _text(value))
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def score_resume(s: Scenario, resume: dict[str, Any]) -> Score:
    score = Score()
    careers = (resume.get("competencies") or {}).get("careers") or []
    known = [c.company for c in s.careers]
    score.extra_careers = sum(
        1
        for c in careers
        if _text(c.get("company_name")) and not _has(c.get("company_name"), *known)
    )
    for fact in s.careers:
        got = next((c for c in careers if _has(c.get("company_name"), fact.company)), None)
        key = fact.company
        if got is None:
            for name in ("회사", "입사", "퇴사", "하던 일", "직급"):
                score.fields[f"{key} {name}"] = MISSING
            score.occupation[key] = MISSING
            continue
        score.fields[f"{key} 회사"] = CORRECT
        start, end = got.get("start_date"), got.get("end_date")
        score.fields[f"{key} 입사"] = _judge(start, _ym(start) == fact.start)
        score.fields[f"{key} 퇴사"] = _judge(end, _ym(end) == fact.end)
        duties = got.get("main_duties")
        score.fields[f"{key} 하던 일"] = _judge(duties, _has(duties, *fact.duties))
        position = got.get("position")
        if fact.position is None:
            # "없었음"이 정답: 비었거나 "없음"이면 맞음, 다른 값(예: 생산직)은 틀림
            empty = not _norm(_text(position)) or _has(position, "없")
            score.fields[f"{key} 직급"] = CORRECT if empty else WRONG
        else:
            score.fields[f"{key} 직급"] = _judge(position, _has(position, fact.position))
        occupation = got.get("occupation")
        if fact.occupation:
            score.occupation[key] = _judge(occupation, _has(occupation, fact.occupation))

    education = resume.get("education") or []
    if s.education:
        levels = " ".join(_text(e.get("level") or e.get("education_level")) for e in education)
        score.fields["학력"] = _judge(levels, s.education[:2] in levels)
    certs = (resume.get("competencies") or {}).get("certifications") or []
    names = " ".join(_text(c.get("certificate_name")) for c in certs)
    for cert in s.certifications:
        score.fields[f"자격 {cert}"] = _judge(names, _has(names, cert))
    prefs = resume.get("job_preferences") or {}
    if s.desired_job:
        jobs = prefs.get("desired_occupations") or []
        score.fields["희망 직종"] = _judge(jobs, _has(jobs, s.desired_job))
    if s.region:
        regions = prefs.get("desired_regions") or []
        score.fields["희망 지역"] = _judge(regions, _has(regions, s.region))
    return score


def is_question(reply: str) -> bool:
    return "?" in reply or bool(re.search(r"(나요|까요|세요|주세요|있으세요|어요\?)\s*$", reply))


def _last_question(reply: str) -> str:
    parts = [p for p in re.split(r"(?<=[?.!])\s+", reply.strip()) if p]
    return next((p for p in reversed(parts) if "?" in p), "")


def _overlap(a: str, b: str) -> float:
    ga = {a[i : i + 2] for i in range(len(a) - 1)}
    gb = {b[i : i + 2] for i in range(len(b) - 1)}
    return len(ga & gb) / max(1, min(len(ga), len(gb)))


def score_dialogue(score: Score, replies: list[str], ended: bool) -> Score:
    score.turns = len(replies)
    score.asked = sum(is_question(r) for r in replies)
    questions = [q for r in replies if (q := _norm(_last_question(r)))]
    score.repeated = sum(
        1
        for i, q in enumerate(questions)
        if any(_overlap(q, p) >= REPEAT_OVERLAP for p in questions[:i])
    )
    score.ended = ended
    return score
