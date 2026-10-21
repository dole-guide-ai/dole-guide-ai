"""골든셋 결과 보고서.

evals/reports/golden-<시각>.md에 쓰고, GitHub Actions에서는 실행 화면 요약에도 붙입니다.

보고서에는 AI 답 원문을 넣지 않습니다(공개 저장소의 실행 기록에 남지 않게). 틀린 이유만 적습니다.
"""

import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPORT_DIR = Path(__file__).parents[1] / "reports"
ORDER = ["통과", "실패", "참고 실패", "판정 건너뜀", "건너뜀"]
AREA_NAMES = {"procedure": "절차", "form_fill": "서류", "grounding": "근거", "masking": "개인정보"}


def _cell(value: Any) -> str:
    """표 한 칸에 넣을 글. 정규식의 |나 줄바꿈이 표를 깨지 않게 바꿉니다."""
    return " ".join(str(value).replace("|", "\\|").splitlines())


@dataclass
class Record:
    case: dict[str, Any]
    status: str = "건너뜀"
    reasons: list[str] = field(default_factory=list)

    def skip(self, reason: str) -> None:
        self.status, self.reasons = "건너뜀", [reason]

    def finish(self, failures: list[str], judged: bool | None) -> None:
        self.reasons = failures
        if failures:
            self.status = "참고 실패" if self.case["review"] == "확인필요" else "실패"
        else:
            self.status = "판정 건너뜀" if judged is None else "통과"


@dataclass
class Report:
    mode: str
    records: list[Record] = field(default_factory=list)

    def start(self, case: dict[str, Any]) -> Record:
        self.records.append(record := Record(case))
        return record

    def counts(self) -> Counter[str]:
        return Counter(record.status for record in self.records)

    def render(self) -> str:
        counts = self.counts()
        graded = counts["통과"] + counts["실패"]
        rate = f"{counts['통과'] / graded:.0%}" if graded else "-"
        lines = [
            f"# 골든셋 결과 ({datetime.now():%Y-%m-%d %H:%M}, 모드 {self.mode})",
            "",
            "| 전체 | " + " | ".join(ORDER) + " | 통과율(확정 문항) |",
            "| --- " * (len(ORDER) + 2) + "|",
            f"| {len(self.records)} | "
            + " | ".join(str(counts[s]) for s in ORDER)
            + f" | {rate} |",
        ]
        for title, key in (("영역별", "area"), ("방법별", "method")):
            lines += ["", f"## {title}", "", "| 구분 | " + " | ".join(ORDER) + " |",
                      "| --- " * (len(ORDER) + 1) + "|"]  # fmt: skip
            groups = Counter((r.case[key], r.status) for r in self.records)
            for name in dict.fromkeys(r.case[key] for r in self.records):
                label = AREA_NAMES.get(name, name)
                lines.append(
                    f"| {label} | " + " | ".join(str(groups[name, s]) for s in ORDER) + " |"
                )
        for status in ("실패", "참고 실패"):
            rows = [r for r in self.records if r.status == status]
            if rows:
                lines += [
                    "",
                    f"## {status} {len(rows)}개",
                    "",
                    "| ID | 설명 | 이유 |",
                    "| --- | --- | --- |",
                ]
                lines += [
                    f"| {_cell(r.case['id'])} | {_cell(r.case['description'])} | "
                    + "<br>".join(_cell(reason) for reason in r.reasons)
                    + " |"
                    for r in rows
                ]
        skipped = Counter(r.reasons[0] for r in self.records if r.status == "건너뜀" and r.reasons)
        if skipped:
            lines += ["", "## 건너뛴 이유", ""] + [f"- {why}: {n}개" for why, n in skipped.items()]
        return "\n".join(lines) + "\n"

    def write(self) -> Path:
        text = self.render()
        REPORT_DIR.mkdir(exist_ok=True)
        path = REPORT_DIR / f"golden-{datetime.now():%Y%m%d-%H%M%S}.md"
        path.write_text(text, encoding="utf-8")
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(text)
        return path
