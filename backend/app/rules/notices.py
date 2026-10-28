"""계정 화면의 인정일 마감과 대시보드 알림. 판정과 문구를 여기 한 곳에서 정합니다. 순수 함수.

- 마감(round_deadline): 인정일까지 남은 날과 지금 시각의 제출 방식(rules/application.submit_mode,
  17시 인터넷·18시 방문 마감)
- 신청 경로(visit): 이직일 만 65세 이상이고 수급자격 신청 전 단계면 센터 방문 신청 (PROC-048)
- 인정일 지남(overdue): 지금 회차 인정일 18시가 지났거나, 지난 회차를 내지 않았는데 인정일부터
  14일이 안 지났으면 변경 신청 안내 (DUE-089·094)
- 출석 회차(attend): 지금 회차가 출석 회차면 직접 방문 (ACT-040). 인정일 지남과는 함께 내지 않음
- 지금 회차 신청서를 이미 냈으면 그 회차의 지남·출석 알림은 내지 않음

문구는 `data/templates/notices.json`에 둡니다.
"""

import json
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from app.rules.application import submit_mode
from app.rules.entry_text import korean_date
from app.rules.presubmit import visit_to_apply
from app.schemas.accounts import Notice, NoticeKind, RoundDeadline
from app.schemas.application import SubmitMode
from app.schemas.procedure import ProcedureRead, Stage
from app.schemas.rounds import ApplicationStatus, RoundStatus, RoundSummary

TEMPLATES_JSON = Path(__file__).resolve().parents[2] / "data" / "templates" / "notices.json"
# 인정일을 놓쳤을 때 변경 신청을 할 수 있는 기간: 인정일부터 14일 (DUE-089)
CHANGE_REQUEST_DAYS = 14


@cache
def templates() -> dict[str, Any]:
    return json.loads(TEMPLATES_JSON.read_text(encoding="utf-8"))


def round_deadline(current: RoundSummary, now: datetime) -> RoundDeadline:
    """인정일까지 남은 날과 지금 시각의 제출 방식(rules/application.submit_mode)."""
    mode = SubmitMode(submit_mode(now, current.recognition_date, current.attendance_required))
    return RoundDeadline(
        d_day=(current.recognition_date - now.date()).days,
        submit_mode=mode,
        overdue=mode == SubmitMode.CHANGE,
    )


def missed_round(rounds: list[RoundSummary], today: date) -> RoundSummary | None:
    """인정일이 지났는데 신청서를 내지 않았고, 아직 변경 신청 기간 안인 가장 최근 회차."""
    missed = [
        r
        for r in rounds
        if r.status == RoundStatus.CLOSED
        and r.application_status != ApplicationStatus.SUBMITTED
        and today <= change_request_until(r.recognition_date)
    ]
    return max(missed, key=lambda r: r.recognition_date, default=None)


def change_request_until(recognition_date: date) -> date:
    return recognition_date + timedelta(days=CHANGE_REQUEST_DAYS)


def account_notices(
    procedure: ProcedureRead,
    current: RoundSummary | None,
    deadline: RoundDeadline | None,
    missed: RoundSummary | None,
) -> list[Notice]:
    notices = []
    if visit_to_apply(procedure.age_at_separation, procedure.stage):
        notices.append(
            _notice(NoticeKind.VISIT, NoticeKind.VISIT.value, age=procedure.age_at_separation)
        )
    if procedure.stage != Stage.RECOGNITION:
        return notices
    # 이미 낸 지금 회차는 놓칠 것도 출석 준비할 것도 없습니다(지난 회차를 놓친 알림만 남김).
    if current is not None and current.application_status == ApplicationStatus.SUBMITTED:
        current = None
    overdue = current if current and deadline and deadline.overdue else missed
    if overdue is not None:
        day = overdue.recognition_date
        notices.append(
            _notice(
                NoticeKind.OVERDUE,
                f"overdue-{day.isoformat()}",
                date=korean_date(day),
                until=korean_date(change_request_until(day)),
            )
        )
    elif current is not None and current.attendance_required:
        notices.append(_notice(NoticeKind.ATTEND, f"attend-{current.round}", round=current.round))
    return notices


def _notice(kind: NoticeKind, key: str, **values: Any) -> Notice:
    spec = templates()[kind.value]
    return Notice(
        kind=kind,
        key=key,
        title=spec["title"].format(**values),
        text=spec["text"].format(**values),
        rule_refs=list(spec["rule_refs"]),
    )
