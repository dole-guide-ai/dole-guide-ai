"""회차 점검 `check_round` (상세기획 2-2.6, 설계 6.2~6.4). 순수 함수입니다.

이번 회차 활동을 8단계로 계산합니다.
1. 대상기간(인정일 당일 포함) 밖이면 `out_of_period`
2. 종류·회차·수급자 유형에서 허용되지 않으면 `not_allowed`, 표에 없는 종류면 `needs_check`
3. 수급 기간 전체 누적 한도(특강 2회 등)를 넘으면 `limit_over`
4. 직업훈련은 날짜 묶기와 따로 시간을 더해 환산
5. 같은 날은 1건만 `counted`, 나머지는 `same_day`
6~7. 인정 건수·구직활동 수를 필요 건수와 비교 (8차부터 일반은 7일마다 구직활동 1건)
8. 사전 경고 W1~W6

규칙 값은 `data/rules/activities.json`(`activity_table`)에서 읽습니다.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.rules.activity_table import ActivityRules, KindRule, load_rules
from app.rules.application import ActivityInput
from app.schemas.activities import ActivityCategory
from app.schemas.rounds import (
    ActivityCheck,
    ActivityStatus,
    CheckStatus,
    LimitsUsed,
    RoundWarning,
    WarningId,
    WeekCheck,
)

DAYS_PER_WEEK = 7
# 같은 회사에 이 횟수 이상 지원하면 W3
SAME_COMPANY_MIN = 2

_W1 = "{day} 활동은 {count}건이지만 하루 1건만 인정돼요."
_W2 = "{day}는 이번 회차 기간({start}~{end}) 밖이라 계산에서 뺐어요."
_W3 = "같은 회사에만 계속 지원하면 인정되지 않을 수 있어요."
_W4 = "{label}은 수급 기간 전체에서 {max}번까지만 인정돼요."
_W5 = "{org} 지원은 {evidence}이 필요해요. 사진으로 올려 주세요."
_W6 = "구직 외 활동만으로는 안 돼요. 입사지원이나 면접 1건이 꼭 필요해요."


@dataclass
class RoundResult:
    """`check_round` 결과. 서비스가 회차 요약(RoundSummary)과 합쳐 응답을 만듭니다."""

    required: int | None
    required_job_search: int | None
    counted: int
    counted_job_search: int
    check_status: CheckStatus
    activities: list[ActivityCheck]
    warnings: list[RoundWarning]
    weeks: list[WeekCheck]
    limits_used: LimitsUsed
    rule_refs: list[str]

    @property
    def remaining(self) -> int:
        return max((self.required or 0) - self.counted, 0)

    @property
    def remaining_job_search(self) -> int:
        return max((self.required_job_search or 0) - self.counted_job_search, 0)


@dataclass
class _Refs:
    items: list[str] = field(default_factory=list)

    def add(self, refs: tuple[str, ...] | list[str]) -> None:
        self.items += [ref for ref in refs if ref not in self.items]


def _short(day: date) -> str:
    return f"{day.month:02d}.{day.day:02d}"


def is_not_allowed(rule: KindRule, rules: ActivityRules, group: str, round_no: int) -> bool:
    """종류·회차·수급자 유형에서 인정되지 않는 활동인지 (2-2.3 표, ACT-030 등)."""
    only_job = rules.job_search_only_from_round
    return (
        not rule.allowed
        or (rule.only_round is not None and rule.only_round != round_no)
        or (bool(rule.groups) and group not in rule.groups)
        or (
            rule.category == ActivityCategory.NON_JOB_SEARCH
            and group in only_job.groups
            and round_no >= only_job.round
        )
    )


def _evidence_ok(activity: ActivityInput, rules: ActivityRules) -> bool:
    route = rules.route(activity.route)
    return activity.has_evidence or (route is not None and not route.evidence)


def _week_slices(start: date, end: date) -> list[tuple[date, date]]:
    weeks = []
    while start <= end:
        week_end = min(start + timedelta(days=DAYS_PER_WEEK - 1), end)
        weeks.append((start, week_end))
        start = week_end + timedelta(days=1)
    return weeks


def check_round(
    *,
    round_no: int,
    group: str,
    period_start: date,
    period_end: date,
    standard_period: bool,
    activities: list[ActivityInput],
    history: list[ActivityInput],
    today: date,
) -> RoundResult:
    """이번 회차 활동을 계산합니다.

    `activities`는 이번 회차에 기록된 활동(기록 순서), `history`는 지난 회차의 실제 활동입니다.
    지난 회차 활동은 누적 한도와 같은 회사 반복(W3)에만 씁니다.
    `standard_period`가 False면(인정일 변경 등) 필요 건수를 셀 수 없어 확인 필요입니다.
    """
    rules = load_rules()
    refs = _Refs()
    status: dict[str, ActivityStatus] = {}
    warnings: list[RoundWarning] = []
    used: Counter[str] = Counter(
        rule.limit_group
        for a in history
        if not a.planned and (rule := rules.kind(a.kind)) and rule.limit_group
    )

    # 1~4단계: 활동마다 계산할 수 있는지 거르고, 날짜 묶기와 직업훈련으로 나눕니다.
    by_day: dict[date, list[ActivityInput]] = {}
    training: list[ActivityInput] = []
    for a in activities:
        rule = rules.kind(a.kind)
        if a.planned or a.activity_date > today:
            status[a.activity_id] = ActivityStatus.PLANNED
        elif not period_start <= a.activity_date <= period_end:
            status[a.activity_id] = ActivityStatus.OUT_OF_PERIOD
            refs.add(rules.period_rule_refs)
            warnings.append(
                RoundWarning(
                    id=WarningId.OUT_OF_PERIOD,
                    message=_W2.format(
                        day=_short(a.activity_date),
                        start=_short(period_start),
                        end=_short(period_end),
                    ),
                    activity_ids=[a.activity_id],
                    rule_refs=list(rules.period_rule_refs),
                )
            )
        elif rule is None:
            status[a.activity_id] = ActivityStatus.NEEDS_CHECK
        elif is_not_allowed(rule, rules, group, round_no):
            status[a.activity_id] = ActivityStatus.NOT_ALLOWED
            refs.add(rule.rule_refs)
        elif rule.limit_group and (limit := rules.limit(rule.limit_group)):
            if used[rule.limit_group] >= limit.max:
                status[a.activity_id] = ActivityStatus.LIMIT_OVER
                refs.add(limit.rule_refs)
                warnings.append(
                    RoundWarning(
                        id=WarningId.LIMIT_OVER,
                        message=_W4.format(label=limit.label, max=limit.max),
                        activity_ids=[a.activity_id],
                        rule_refs=list(limit.rule_refs),
                    )
                )
            else:
                used[rule.limit_group] += 1
                by_day.setdefault(a.activity_date, []).append(a)
        elif rule.by_hours:
            training.append(a)
        else:
            by_day.setdefault(a.activity_date, []).append(a)

    # 5단계: 같은 날은 구직활동 > 구직 외 > 증빙 갖춤 > 먼저 기록 순으로 1건만 셉니다.
    counted: list[ActivityInput] = []
    order = {a.activity_id: i for i, a in enumerate(activities)}
    for day in sorted(by_day):
        same_day = sorted(
            by_day[day],
            key=lambda a: (
                a.category != ActivityCategory.JOB_SEARCH,
                not _evidence_ok(a, rules),
                order[a.activity_id],
            ),
        )
        first, *rest = same_day
        counted.append(first)
        status[first.activity_id] = ActivityStatus.COUNTED
        for other in rest:
            status[other.activity_id] = ActivityStatus.SAME_DAY
        if rest:
            refs.add(rules.same_day_rule_refs)
            warnings.append(
                RoundWarning(
                    id=WarningId.SAME_DAY,
                    message=_W1.format(day=_short(day), count=len(same_day)),
                    activity_ids=[a.activity_id for a in same_day],
                    rule_refs=list(rules.same_day_rule_refs),
                )
            )

    # 4단계: 직업훈련은 과정 구분 없이 시간을 더해 환산합니다.
    hours_rule = rules.training_hours
    hours = sum(a.hours or 0 for a in training)
    training_full = hours >= hours_rule.full_round
    training_job = 1 if hours_rule.min_counted <= hours < hours_rule.full_round else 0
    for a in training:
        if a.hours is None:
            status[a.activity_id] = ActivityStatus.NEEDS_CHECK
        else:
            counts = hours >= hours_rule.min_counted
            status[a.activity_id] = ActivityStatus.COUNTED if counts else ActivityStatus.NOT_ALLOWED
    if training:
        refs.add(hours_rule.rule_refs)

    # 6~7단계: 필요 건수와 비교합니다.
    row = rules.required_row(group, round_no)
    if row is not None:
        refs.add(rules.required.rule_refs)
    jobs = [a for a in counted if a.category == ActivityCategory.JOB_SEARCH]
    total = len(counted) + training_job
    total_job = len(jobs) + training_job
    weeks: list[WeekCheck] = []
    required: int | None
    required_job: int | None
    if row is None:
        # 반복수급자 등 지원하지 않는 유형
        required = required_job = None
    elif row.weekly_job_search:
        weeks = [
            WeekCheck(
                start=start,
                end=end,
                job_search=sum(1 for a in jobs if start <= a.activity_date <= end),
            )
            for start, end in _week_slices(period_start, period_end)
        ]
        required = required_job = len(weeks)
        total_job = sum(1 for week in weeks if week.job_search > 0)
        total = total_job
    elif row.first_education:
        required, required_job = row.total, row.job_search
        total = min(sum(1 for a in counted if a.kind == "first_education"), row.total)
        total_job = 0
    else:
        required, required_job = row.total, row.job_search
    if training_full and required is not None and not row.first_education:
        total, total_job = required, required_job or 0

    if required is None or not standard_period:
        check_status = CheckStatus.NEEDS_CHECK
        refs.add(rules.period_rule_refs)
    elif total >= required and total_job >= (required_job or 0):
        check_status = CheckStatus.SATISFIED
    else:
        check_status = CheckStatus.SHORT

    # 8단계: 나머지 사전 경고
    warnings += _evidence_warnings(activities, status, rules, refs)
    warnings += _same_company_warnings(activities, history, status, rules, refs)
    if (
        required is not None
        and not row.weekly_job_search
        and total >= required
        and total_job < (required_job or 0)
    ):
        warnings.append(
            RoundWarning(
                id=WarningId.NO_JOB_SEARCH,
                message=_W6,
                rule_refs=list(rules.required.rule_refs),
            )
        )

    checks = [_activity_check(a, status[a.activity_id], rules) for a in activities]
    for a in activities:
        if rule := rules.kind(a.kind):
            refs.add(rule.rule_refs)
    return RoundResult(
        required=required,
        required_job_search=required_job,
        counted=total,
        counted_job_search=total_job,
        check_status=check_status,
        activities=checks,
        warnings=warnings,
        weeks=weeks,
        limits_used=LimitsUsed(**{g: used[g] for g in LimitsUsed.model_fields}),
        rule_refs=refs.items,
    )


def _activity_check(
    a: ActivityInput, status: ActivityStatus, rules: ActivityRules
) -> ActivityCheck:
    route = rules.route(a.route)
    kind = rules.kind(a.kind)
    return ActivityCheck(
        activity_id=a.activity_id,
        activity_date=a.activity_date,
        category=ActivityCategory(a.category),
        kind=a.kind,
        route=a.route,
        org_name=a.org_name,
        job_title=a.job_title,
        source=a.source,
        planned=a.planned,
        status=status,
        required_evidence=list(route.evidence) if route else None,
        has_evidence=a.has_evidence,
        rule_refs=[*(kind.rule_refs if kind else ()), *(route.rule_refs if route else ())],
    )


def _evidence_warnings(
    activities: list[ActivityInput],
    status: dict[str, ActivityStatus],
    rules: ActivityRules,
    refs: _Refs,
) -> list[RoundWarning]:
    """W5: 증빙이 필요한 활동인데 파일이 없음. 계산에 들어갈 수 있는 활동만 봅니다."""
    warnings = []
    for a in activities:
        route = rules.route(a.route)
        counts = status[a.activity_id] in (ActivityStatus.COUNTED, ActivityStatus.SAME_DAY)
        if counts and route and route.evidence and not a.has_evidence:
            refs.add(route.rule_refs)
            warnings.append(
                RoundWarning(
                    id=WarningId.NO_EVIDENCE,
                    message=_W5.format(
                        org=a.org_name or route.label, evidence=" + ".join(route.evidence)
                    ),
                    activity_ids=[a.activity_id],
                    rule_refs=list(route.rule_refs),
                )
            )
    return warnings


def _org_key(name: str | None) -> str:
    return "".join((name or "").split())


def _same_company_warnings(
    activities: list[ActivityInput],
    history: list[ActivityInput],
    status: dict[str, ActivityStatus],
    rules: ActivityRules,
    refs: _Refs,
) -> list[RoundWarning]:
    """W3: 이번 회차에 같은 회사에 두 번 이상 지원했거나, 지난 회차부터 같은 회사에만 지원함."""
    jobs = [
        a
        for a in activities
        if a.category == ActivityCategory.JOB_SEARCH
        and _org_key(a.org_name)
        and status[a.activity_id] not in (ActivityStatus.PLANNED, ActivityStatus.OUT_OF_PERIOD)
    ]
    by_org: dict[str, list[ActivityInput]] = {}
    for a in jobs:
        by_org.setdefault(_org_key(a.org_name), []).append(a)
    past = {
        _org_key(a.org_name)
        for a in history
        if a.category == ActivityCategory.JOB_SEARCH and not a.planned and _org_key(a.org_name)
    }
    repeated = [
        group
        for org, group in by_org.items()
        if len(group) >= SAME_COMPANY_MIN or (len(by_org) == 1 and past == {org})
    ]
    if not repeated:
        return []
    refs.add(rules.same_company_rule_refs)
    return [
        RoundWarning(
            id=WarningId.SAME_COMPANY,
            message=_W3,
            activity_ids=[a.activity_id for group in repeated for a in group],
            rule_refs=list(rules.same_company_rule_refs),
        )
    ]
