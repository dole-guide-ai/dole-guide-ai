"""부족한 활동 추천 (`recommend_activities`, 상세기획 2-2.8). DB와 HTTP를 모르는 순수 함수입니다.

후보는 활동 종류 표(2-2.3)·증빙 표(2-2.4)에서 이번 회차·규칙 그룹에 허용되고
누적 한도가 남은 종류입니다. 순서는 증빙이 쉬운 경로 먼저(고용24 입사지원·온라인 취업특강 = 증빙
불필요), 같으면 구직활동 먼저, 직업훈련은 수강 신청·개강 일정이 있어 맨 아래입니다.
구직활동이 부족하면 구직활동 후보를 위로 올립니다.
공고 추천은 하지 않습니다(MVP 제외). 최대 3개.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.rules.application import GENERAL_RULE_GROUPS, JOB_SEARCH, NON_JOB_SEARCH

MAX_ITEMS = 3
# 일반 규칙 그룹(반복수급자 포함)은 8차부터 구직활동만 인정합니다 (ACT-030).
JOB_SEARCH_ONLY_FROM = 8
# 단기·온라인 취업특강은 합쳐서 수급 기간 전체 2회까지 (ACT-043, ACT-117).
LECTURE_LIMIT = 2
_WEEKDAYS = "월화수목금토일"


@dataclass(frozen=True)
class Candidate:
    key: str
    category: str
    kind: str
    route: str
    title: str
    evidence: str | None
    rule_refs: tuple[str, ...]
    is_training: bool = False


# 기본 순서는 상세기획 2-2.8 이정호 예시(고용24 입사지원 → 온라인 특강 → 면접)를 따릅니다.
CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        "work24_apply",
        JOB_SEARCH,
        "job_application",
        "work24",
        "입사지원 (고용24)",
        None,
        ("ACT-001", "ACT-132"),
    ),
    Candidate(
        "step_lecture",
        NON_JOB_SEARCH,
        "lecture",
        "step_online",
        "온라인 취업특강 (STEP) — 1과정 끝까지(진도율 100%)",
        None,
        ("ACT-043", "ACT-117"),
    ),
    Candidate(
        "interview",
        JOB_SEARCH,
        "interview",
        "interview",
        "면접 (잡힌 면접이 있으면)",
        "면접확인서 + 명함",
        ("ACT-002", "ACT-137"),
    ),
    Candidate(
        "company_site_apply",
        JOB_SEARCH,
        "job_application",
        "company_site",
        "입사지원 (기업 홈페이지)",
        "채용공고 + 지원 완료 화면 캡처(날짜가 보이게)",
        ("ACT-001", "ACT-136"),
    ),
    Candidate(
        "training",
        NON_JOB_SEARCH,
        "training",
        "training",
        "직업훈련 수강",
        "수강증명서 + 대상 기간 출석부",
        ("ACT-051", "ACT-141"),
        is_training=True,
    ),
)
BY_KEY = {candidate.key: candidate for candidate in CANDIDATES}


@dataclass(frozen=True)
class Recommendation:
    candidate: Candidate
    title: str
    reason: str


WEEKLY_TEXT = (
    " 8차부터는 매주 구직활동 1건이 필요해요. 주를 나누는 기준은 고용센터 안내를 따라 주세요."
)


def is_weekly_job_search(group: str, round_no: int) -> bool:
    """일반 규칙 그룹 8차부터는 1주에 구직활동 1건이라 회차 합계만으로는 충족을 알 수 없습니다.

    주 단위 계산은 회차 점검(F-18)이 정하므로(상세기획 2-2.6 `확인 필요`),
    추천은 늘 구직활동을 권합니다.
    """
    return group in GENERAL_RULE_GROUPS and round_no >= JOB_SEARCH_ONLY_FROM


def _allowed(candidate: Candidate, group: str, round_no: int, lectures_used: int) -> bool:
    job_search_only = group in GENERAL_RULE_GROUPS and round_no >= JOB_SEARCH_ONLY_FROM
    if candidate.category == NON_JOB_SEARCH and job_search_only:
        return False
    return not (candidate.kind == "lecture" and lectures_used >= LECTURE_LIMIT)


def recommend_activities(
    *,
    shortfall: int,
    shortfall_job_search: int,
    group: str,
    round_no: int,
    lectures_used: int,
    desired_occupation: str | None,
) -> list[Recommendation]:
    """부족한 만큼 할 수 있는 활동을 최대 3개 고릅니다. 부족이 없으면 빈 목록입니다."""
    if shortfall <= 0 and shortfall_job_search <= 0:
        return []
    needs_job = shortfall_job_search > 0
    candidates = [c for c in CANDIDATES if _allowed(c, group, round_no, lectures_used)]
    ranked = sorted(
        candidates,
        key=lambda c: (
            needs_job and c.category != JOB_SEARCH,
            c.is_training,
            c.evidence is not None,
            c.category != JOB_SEARCH,
            CANDIDATES.index(c),
        ),
    )
    return [_describe(c, needs_job, lectures_used, desired_occupation) for c in ranked[:MAX_ITEMS]]


def _describe(
    candidate: Candidate, needs_job: bool, lectures_used: int, occupation: str | None
) -> Recommendation:
    title = candidate.title
    if candidate.key == "work24_apply" and occupation:
        title = f"{title} — 희망 직종 ‘{occupation}’ 공고"
    parts = ["구직활동" if candidate.category == JOB_SEARCH else "구직 외 활동"]
    parts.append(f"증빙 {candidate.evidence}" if candidate.evidence else "증빙 불필요")
    if candidate.kind == "lecture":
        parts.append(f"한도 {LECTURE_LIMIT}회 중 {lectures_used}회 사용")
    if needs_job and candidate.category != JOB_SEARCH:
        parts.append("구직활동 1건은 따로 필요해요")
    return Recommendation(candidate=candidate, title=title, reason=" · ".join(parts))


def recommendation_id(round_no: int, key: str) -> str:
    return f"rec_{round_no}_{key}"


def parse_recommendation_id(value: str) -> tuple[int, Candidate] | None:
    """`rec_{회차}_{종류}`를 회차 번호와 후보로 나눕니다. 모양이 다르면 None."""
    prefix, _, rest = value.partition("_")
    round_text, _, key = rest.partition("_")
    if prefix != "rec" or not round_text.isdigit() or key not in BY_KEY:
        return None
    return int(round_text), BY_KEY[key]


def deadline_text(recognition_date: date, busy_dates: list[date], weekly: bool = False) -> str:
    """언제까지: 인정일 당일 활동도 인정되지만 추천은 전날까지로 권장합니다 (CHECK-011)."""
    by = recognition_date - timedelta(days=1)
    text = f"{_short(by)}까지 해 두세요."
    if busy_dates:
        days = ", ".join(_short(day) for day in sorted(set(busy_dates)))
        text += f" 이미 활동이 있는 날({days})은 하루 1건만 인정되니 피해 주세요."
    if weekly:
        text += WEEKLY_TEXT
    return text


def _short(day: date) -> str:
    return f"{day.month}.{day.day}({_WEEKDAYS[day.weekday()]})"


def planned_date(recognition_date: date, today: date) -> date:
    """추천을 예정으로 넣을 때의 날짜: 권장 기한인 인정일 전날.

    오늘이 인정일이면 전날은 이미 지났으므로 오늘(인정일 당일 활동도 인정, CHECK-011)로 둡니다.
    """
    return max(recognition_date - timedelta(days=1), today)
