"""이력서 인터뷰 보고서(evals/reports/interview-<시각>.md).

시나리오별 점수와 대화 기록을 남깁니다.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from evals.interview.scoring import CORRECT, MISSING, WRONG, Score

REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"


@dataclass
class Run:
    scenario_id: str
    title: str
    score: Score
    transcript: list[tuple[str, str]]


@dataclass
class InterviewReport:
    runs: list[Run] = field(default_factory=list)

    def write(self) -> Path:
        REPORT_DIR.mkdir(exist_ok=True)
        # 조각을 동시에 돌리면 같은 초에 끝날 수 있어 프로세스 번호를 붙입니다.
        path = REPORT_DIR / f"interview-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}.md"
        path.write_text(self.markdown(), encoding="utf-8")
        return path

    def totals(self) -> dict[str, float]:
        scores = [r.score for r in self.runs]
        total = sum(s.total for s in scores) or 1
        turns = sum(s.turns for s in scores) or 1
        occ = [v for s in scores for v in s.occupation.values()]
        return {
            "correct": sum(s.correct for s in scores) / total,
            "wrong": sum(s.wrong for s in scores) / total,
            "missing": sum(sum(v == MISSING for v in s.fields.values()) for s in scores) / total,
            "asked": sum(s.asked for s in scores) / turns,
            "repeated": sum(s.repeated for s in scores),
            "extra_careers": sum(s.extra_careers for s in scores),
            "turns": sum(s.turns for s in scores) / max(1, len(scores)),
            "ended": sum(s.ended for s in scores),
            "occupation": sum(v == CORRECT for v in occ) / max(1, len(occ)),
        }

    def markdown(self) -> str:
        settings = get_settings()
        t = self.totals()
        lines = [
            f"# 이력서 인터뷰 결과 ({datetime.now():%Y-%m-%d %H:%M})",
            "",
            f"에이전트 {settings.agent_model} · "
            f"가상 사용자 {settings.judge_model or '(agent와 같음)'}",
            "",
            "| 칸 맞음 | 틀림 | 비어 있음 | 물은 턴 비율 | 반복 질문 | 지어낸 경력 "
            "| 평균 턴 | 끝까지 안내 | 직종(참고) |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            f"| {t['correct']:.0%} | {t['wrong']:.0%} | {t['missing']:.0%} | {t['asked']:.0%} "
            f"| {t['repeated']:.0f} | {t['extra_careers']:.0f} | {t['turns']:.1f} "
            f"| {t['ended']:.0f}/{len(self.runs)} | {t['occupation']:.0%} |",
            "",
            "## 시나리오별",
            "",
            "| ID | 설명 | 맞음 | 틀림 | 턴 | 물음 | 반복 | 틀리거나 빈 칸 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in self.runs:
            s = r.score
            bad = ", ".join(f"{k}({v})" for k, v in s.fields.items() if v != CORRECT)
            lines.append(
                f"| {r.scenario_id} | {r.title} | {s.correct}/{s.total} | {s.wrong} | {s.turns} "
                f"| {s.asked} | {s.repeated} | {bad or '-'} |"
            )
        lines += ["", "## 대화 기록", ""]
        for r in self.runs:
            lines += [f"### {r.scenario_id} {r.title}", ""]
            for user, agent in r.transcript:
                lines += [f"- 사용자: {user}", f"  - AI: {agent.replace(chr(10), ' / ')}"]
            lines.append("")
        return "\n".join(lines)


__all__ = ["CORRECT", "WRONG", "MISSING", "InterviewReport", "Run"]
