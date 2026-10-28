"""활동 규칙 표(data/rules/activities.json)를 읽는 로직.

값(활동 종류·누적 한도·경로별 증빙·회차별 필요 건수)은 JSON에만 두고, 계산 순서는 규칙 함수
(`app/rules/rounds.py` 등)에 둡니다. 행마다 `rule_refs`가 있어 응답의 근거 줄로 나갑니다.
처음 쓸 때 한 번 읽고, 형식이 틀리면 ValidationError로 바로 실패합니다.
"""

import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.schemas.activities import ActivityCategory

RULES_JSON = Path(__file__).resolve().parents[2] / "data" / "rules" / "activities.json"


class _Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class KindRule(_Row):
    kind: str
    label: str
    category: ActivityCategory
    rule_refs: tuple[str, ...]
    limit_group: str | None = None
    # 이 수급자 유형에만 인정. 비어 있으면 모든 유형
    groups: tuple[str, ...] = ()
    allowed: bool = True
    only_round: int | None = None
    # 직업훈련처럼 날짜 묶기 대신 시간 합으로 인정
    by_hours: bool = False
    # 사용자가 이 활동을 부르는 말(이름 label 말고). 말에 나오면 인정 여부·한도를 안내합니다.
    mentions: tuple[str, ...] = ()


class LimitRule(_Row):
    group: str
    label: str
    max: int
    rule_refs: tuple[str, ...]


class TrainingRule(_Row):
    min_counted: int
    full_round: int
    rule_refs: tuple[str, ...]


class JobSearchOnlyRule(_Row):
    round: int
    groups: tuple[str, ...]
    rule_refs: tuple[str, ...]


class RouteRule(_Row):
    route: str
    label: str
    evidence: tuple[str, ...]
    rule_refs: tuple[str, ...]


class RequiredRow(_Row):
    # [첫 회차, 끝 회차]. 끝이 null이면 마지막 회차까지
    rounds: tuple[int, int | None]
    groups: tuple[str, ...]
    total: int = 0
    job_search: int = 0
    first_education: bool = False
    weekly_job_search: bool = False
    # N일마다 재취업활동 1건 (반복수급자 2주에 1회). 회차 대상기간을 N일씩 나눠 셉니다.
    every_days: int | None = None

    def matches(self, group: str, round_no: int) -> bool:
        first, last = self.rounds
        return group in self.groups and first <= round_no and (last is None or round_no <= last)


class RequiredRule(_Row):
    rule_refs: tuple[str, ...]
    rows: tuple[RequiredRow, ...]


class Review(_Row):
    status: str
    reviewer: str | None
    reviewed_on: date | None


class ActivityRules(_Row):
    effective_from: date
    source: str
    review: Review
    kinds: tuple[KindRule, ...]
    limits: tuple[LimitRule, ...]
    training_hours: TrainingRule
    # 이 회차부터 구직활동만 인정 (일반 8차, 반복수급자 3차)
    job_search_only_from_round: tuple[JobSearchOnlyRule, ...]
    routes: tuple[RouteRule, ...]
    required: RequiredRule
    same_day_rule_refs: tuple[str, ...]
    period_rule_refs: tuple[str, ...]
    same_company_rule_refs: tuple[str, ...]

    def kind(self, kind: str) -> KindRule | None:
        return next((row for row in self.kinds if row.kind == kind), None)

    def limit(self, group: str) -> LimitRule | None:
        return next((row for row in self.limits if row.group == group), None)

    def route(self, route: str | None) -> RouteRule | None:
        return next((row for row in self.routes if row.route == route), None)

    def required_row(self, group: str, round_no: int) -> RequiredRow | None:
        return next((row for row in self.required.rows if row.matches(group, round_no)), None)

    def kinds_mentioned(self, text: str) -> list[KindRule]:
        """말에 이름(label)이나 부르는 말(mentions)이 나온 활동 종류. 띄어쓰기는 무시합니다."""
        compact = re.sub(r"\s+", "", text)
        return [
            row
            for row in self.kinds
            if any(re.sub(r"\s+", "", w) in compact for w in (row.label, *row.mentions))
        ]


@lru_cache(maxsize=1)
def load_rules(path: Path = RULES_JSON) -> ActivityRules:
    return ActivityRules.model_validate_json(path.read_text(encoding="utf-8"))


def required_evidence(route: str | None) -> tuple[str, ...] | None:
    """경로별 필요 증빙 (상세기획 2-2.4). 표에 없는 경로면 None(확인 필요)입니다."""
    row = load_rules().route(route)
    return row.evidence if row else None
