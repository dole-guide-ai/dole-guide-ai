"""이번 턴 답에 꼭 들어가야 할 사실(의무사항)을 코드가 정합니다. LLM·DB 없음.

규칙 함수가 이미 계산한 사실(건수·주기·같은 날·마감·인정 안 되는 활동)을 모델의 재량에 맡기면
빠뜨리거나 다르게 말합니다(골든셋 2차 측정 D2). 그래서
1. 모델 프롬프트에 "반드시 답에 넣을 사실"로 주고(prompt_block),
2. 턴을 마칠 때 답에 빠진 것만 그 문장을 덧붙입니다(missing, nodes/finish).
모델이 먼저 말했으면 코드는 덧붙이지 않습니다. 문장은 지금 상황 문장(rules/briefing)과 회차
경고(rules/rounds)를 그대로 써서, 같은 사실을 두 곳에서 다르게 쓰지 않습니다.

전달 여부는 `tokens`로 봅니다. 묶음마다 하나 이상이 답에 있으면 전달된 것입니다.
예: 같은 날 규칙은 (("같은 날", "하루 1건"), ("다른 날",)) → 두 묶음 모두 답에 있어야 합니다.
"""

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from app.rules.activity_table import load_rules
from app.rules.application import SEND_DEADLINE_HOUR, VISIT_DEADLINE_HOUR
from app.rules.briefing import (
    DAYS_PER_WEEK,
    FIRST_ROUND_EDUCATION,
    GENERAL,
    OUT_OF_PERIOD,
    SAME_DAY,
    deadline_lines,
    md,
    not_counted_lines,
)
from app.rules.rounds import LIMIT_TEXT, NOT_ALLOWED_TEXT, admission, topic
from app.schemas.activities import ActivityCategory
from app.schemas.rounds import ActivityStatus, LimitsUsed

# 직업훈련 시간 기준(규칙표 training_hours). 시간 합으로 인정합니다.
HOURS_TEXT = (
    "{label} 대상기간 안에 {min}시간 이상 들어야 1건으로 인정되고, "
    "{full}시간 이상이면 그 회차 활동을 모두 채운 것으로 봐요."
)

# 회차 사실을 의무로 거는 패널. 이력서·안내 패널에서 회차 숫자를 덧붙이면 질문과 어긋납니다.
ROUND_PANELS = frozenset({"round", "application"})
RECORD_ACTIVITY = "record_activity"
# 덧붙이는 문장 앞 빈 줄(모델이 쓴 문단과 붙지 않게)
GAP = "\n\n"


@dataclass(frozen=True)
class Obligation:
    key: str
    text: str
    tokens: tuple[tuple[str, ...], ...]
    rule_refs: tuple[str, ...] = ()

    def satisfied_by(self, answer: str) -> bool:
        return all(any(token in answer for token in group) for group in self.tokens)

    def as_state(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_state(cls, raw: dict[str, Any]) -> Obligation:
        return cls(
            key=raw["key"],
            text=raw["text"],
            tokens=tuple(tuple(group) for group in raw["tokens"]),
            rule_refs=tuple(raw.get("rule_refs", ())),
        )


def missing(obligations: list[Obligation], answer: str) -> list[Obligation]:
    """답에 빠진 의무사항. 같은 key는 한 번만 봅니다."""
    seen: set[str] = set()
    out = []
    for o in obligations:
        if o.key in seen:
            continue
        seen.add(o.key)
        if not o.satisfied_by(answer):
            out.append(o)
    return out


# 모델이 의무사항 문장을 그대로 베껴 같은 안내를 두 번 쓰지 않게 합니다.
PROMPT_RULE = (
    "아래 사실은 답에 꼭 담는다. 숫자·날짜·횟수는 바꾸지 않고 문장은 자연스럽게 바꿔 써도 된다. "
    "이미 같은 뜻을 말했으면 다시 쓰지 않는다. 되묻기(ask_user) 전에도 먼저 답한다."
)


def prompt_block(obligations: list[Obligation]) -> str:
    """시스템 프롬프트에 넣을 블록. 의무사항이 없으면 빈 글."""
    if not obligations:
        return ""
    lines = "\n".join(f"- {o.text}" for o in obligations)
    return f"## 반드시 답에 담을 사실 (코드가 확정함)\n{PROMPT_RULE}\n{lines}"


def merge(current: list[dict[str, Any]], new: list[Obligation]) -> list[dict[str, Any]]:
    """상태에 저장된 의무사항에 새 것을 key 기준으로 더합니다(체크포인트에 남는 dict)."""
    keys = {raw["key"] for raw in current}
    return [*current, *(o.as_state() for o in new if o.key not in keys)]


# ── 지금 상황(회차 계산)에서 ───────────────────────────────────────


def from_round(
    round_: dict[str, Any] | None, panel: str | None, group: str | None = None
) -> list[Obligation]:
    """회차 패널에서 남은 건수·구직활동·주기·인정 안 된 활동의 이유, 1차 교육."""
    if not round_ or panel not in ROUND_PANELS:
        return []
    refs = tuple(round_.get("rule_refs") or ())
    out: list[Obligation] = []
    if round_.get("round") == 1:
        # 1차는 실업인정 교육이 활동 1건입니다(ACT-020~022). 교육 방식은 수급자 유형마다 다릅니다.
        how = FIRST_ROUND_EDUCATION.get(group or GENERAL, FIRST_ROUND_EDUCATION[GENERAL])
        text = f"1차는 실업인정 교육을 들으면 활동 1건으로 채워져요. {how}"
        out.append(Obligation("round:first_education", text, (("교육",),), refs))
    elif round_.get("required") and not round_.get("required_job_search"):
        out.append(
            Obligation(
                "round:non_job_search_ok",
                "이 회차는 입사지원·면접 말고 취업특강·직업훈련 같은 "
                "구직 외 활동으로도 채울 수 있어요.",
                (("구직 외", "특강", "훈련"),),
                refs,
            )
        )
    remaining = round_.get("remaining")
    if round_.get("required") is not None and remaining:
        out.append(
            Obligation(
                "round:remaining",
                f"이번 회차는 {remaining}건 더 해야 해요.",
                ((f"{remaining}건",),),
                refs,
            )  # fmt: skip
        )
    job = round_.get("remaining_job_search") or 0
    if job and not round_.get("job_search_only"):
        out.append(
            Obligation(
                "round:job_search",
                f"그중 구직활동(입사지원·면접 등)이 {job}건 꼭 들어가야 해요. "
                "취업특강 같은 다른 활동만으로는 채울 수 없어요.",
                (("구직활동",),),
                refs,
            )
        )
    if days := round_.get("interval_days"):
        out.append(_interval(days, bool(round_.get("job_search_only")), refs))
    out += _not_counted(round_)
    return out


def _interval(days: int, job_search_only: bool, refs: tuple[str, ...]) -> Obligation:
    weeks, rest = divmod(days, DAYS_PER_WEEK)
    span = f"{weeks}주" if not rest else f"{days}일"
    kind = "구직활동" if job_search_only else "활동"
    tokens = (span, f"{days}일마다", "매주") if weeks == 1 and not rest else (span, f"{days}일")
    return Obligation(
        "round:interval", f"이 회차는 {span}마다 {kind}을 1건씩 해야 해요.", (tokens,), refs
    )


def _not_counted(round_: dict[str, Any]) -> list[Obligation]:
    start = date.fromisoformat(round_["period_start"])
    end = date.fromisoformat(round_["period_end"])
    # 건수를 이미 채웠으면 "다른 날 더 하라"는 필요 없고, 같은 날 1건이라는 이유만 알립니다.
    short = bool(round_.get("remaining"))
    out = []
    for item in round_.get("not_counted") or []:
        text = not_counted_lines([item], start, end)[0]
        if item["status"] == SAME_DAY:
            reason = ("같은 날", "하루 1건")
            tokens: tuple[tuple[str, ...], ...] = (reason, ("다른 날",)) if short else (reason,)
            if not short:
                text = text.split(". ")[0] + "."
        elif item["status"] == OUT_OF_PERIOD:
            tokens = (("기간",),)
        else:
            continue
        out.append(Obligation(f"round:{item['status']}:{item['date']}", text, tokens))
    return out


def from_deadline(round_: dict[str, Any] | None) -> list[Obligation]:
    """실업인정일 당일(출석 회차 아님)의 인터넷·방문 마감. 지금 시각에 맞는 문장."""
    if not round_ or round_.get("d_day") != 0 or round_.get("attendance_required"):
        return []
    now_time = round_.get("now_time")
    hour = int(now_time.split(":")[0]) if now_time else 0
    send = (f"{SEND_DEADLINE_HOUR}시", f"{SEND_DEADLINE_HOUR}:00")
    visit = (f"{VISIT_DEADLINE_HOUR}시", f"{VISIT_DEADLINE_HOUR}:00")
    if hour >= VISIT_DEADLINE_HOUR:
        tokens: tuple[tuple[str, ...], ...] = (("지났",), ("고용센터",))
    elif hour >= SEND_DEADLINE_HOUR:
        tokens = (("지났",), visit)
    else:
        tokens = (send,)
    text = deadline_lines(0, now_time)[0]
    return [Obligation("deadline", text, tokens, ("DUE-092", "DUE-093"))]


# ── 도구 결과에서 ─────────────────────────────────────────────────


def from_tool_result(name: str, result: dict[str, Any]) -> list[Obligation]:
    """활동 기록 결과: 인정되지 않아 넣지 않았거나, 예정으로 넣었으면 그 사실."""
    if name != RECORD_ACTIVITY:
        return []
    refused = result.get("admission")
    if result.get("recorded") is False and refused:
        refs = tuple(refused.get("rule_refs") or ())
        tokens = (
            (("인정되지 않", "인정이 안", "인정 안"),)
            if refused["status"] == ActivityStatus.NOT_ALLOWED
            else ((f"{refused['limit_max']}번", f"{refused['limit_max']}회"),)
        )
        return [Obligation(f"admission:{refused['kind']}", refused["message"], tokens, refs)]
    if result.get("planned"):
        day = date.fromisoformat(result["activity_date"])
        return [
            Obligation(
                f"planned:{result['activity_date']}",
                f"{md(day)} 활동은 예정으로 적었어요. "
                "한 뒤에 증빙을 올려 주시면 인정 건수에 들어가요.",
                (("예정",),),
            )
        ]
    return []


# ── 말의 범위(라우터 scope)와 개인정보에서 ────────────────────────

# 고용센터가 판단할 일·다른 기관 일에 붙이는 확인 안내. 출력 관문(agent/output)도 씁니다.
CENTER_CHECK = "정확한 내용은 고용노동부 고객상담센터(1350)나 관할 고용센터에 확인해 주세요."
_CHECK_TOKENS = (("1350", "고용센터"),)
_SCOPE_TEXTS = {
    "center_judgment": (
        "사람마다 다른 판단은 관할 고용센터가 해요. " + CENTER_CHECK,
        _CHECK_TOKENS,
    ),
    "out_of_scope": (
        "이 내용은 실업급여 길잡이가 확정해 안내할 수 있는 범위가 아니에요. " + CENTER_CHECK,
        _CHECK_TOKENS,
    ),
    "privacy": (
        "올린 사진·음성 원본은 내용을 읽은 뒤 삭제해요. "
        "저장된 내 정보는 화면의 '내 정보'에서 직접 보고 지울 수 있어요.",
        (("삭제", "지울", "지워"), ("내 정보",)),
    ),
}
# 가린 개인정보 종류(input/pii.PiiKind 값) 중 "저장하지 않음 + 내 정보 화면" 안내를 붙이는 것
_PROFILE_KINDS = frozenset(
    {"rrn", "foreigner_rrn", "card", "account", "phone", "email", "name", "number"}
)
_PII_TEXTS = {
    "profile": (
        "주민등록번호·전화번호·계좌번호·이름 같은 개인정보는 저장하지 않아요. "
        "이름·연락처·계좌 같은 내 정보는 화면의 '내 정보'에서 직접 보고 관리해요.",
        (("저장하지", "저장 안"), ("내 정보",)),
    ),
    "secret": (
        "비밀번호는 받지 않고 대신 로그인하지 않아요.",
        (("비밀번호",),),
    ),
    "sensitive": (
        "건강·다툼·종교 같은 사정은 서류 칸에 적지 않아요. "
        "고용24 이직사유는 정해진 선택지에서 고르면 돼요.",
        (("선택지",),),
    ),
}


def from_scope(scope: str | None) -> list[Obligation]:
    """개인별 판단·다른 기관 일·개인정보 처리 질문에 붙일 안내(라우터 nodes/route.Scope)."""
    if scope not in _SCOPE_TEXTS:
        return []
    text, tokens = _SCOPE_TEXTS[scope]
    return [Obligation(f"scope:{scope}", text, tokens)]


def from_pii(kinds: list[str]) -> list[Obligation]:
    """이번 말에 든 개인정보·민감한 사정(input/pii.kinds_in)에 붙일 안내."""
    groups = []
    if _PROFILE_KINDS & set(kinds):
        groups.append("profile")
    groups += [kind for kind in ("secret", "sensitive") if kind in kinds]
    return [Obligation(f"pii:{g}", *_PII_TEXTS[g]) for g in groups]


# ── 사용자가 말한 활동 종류(규칙표 activities.json)에서 ───────────────

# 활동 종류를 말했을 때 인정 여부·한도·시간 기준을 거는 패널(이력서는 제외)
MENTION_PANELS = frozenset({"round", "guide", "application"})
_NOT_ALLOWED_TOKENS = (("인정되지 않", "인정이 안", "인정 안", "인정하지 않", "인정되지 않아"),)
_SPOKEN_TIMES = {1: "한 번", 2: "두 번", 3: "세 번"}


def from_mentions(
    text: str,
    panel: str | None,
    *,
    group: str | None,
    round_no: int | None,
    limits_used: dict[str, int] | None = None,
) -> list[Obligation]:
    """말에 나온 구직 외 활동 종류마다 인정 여부·누적 한도·훈련 시간 기준(규칙표의 행 그대로).

    회차를 알면 기록 전 판정(rules/rounds.admission)과 같은 기준으로 이번 회차 인정 여부를,
    모르면(실업인정 전 단계) 수급자 유형으로 정해지는 것만 알립니다.
    """
    if panel not in MENTION_PANELS or not group:
        return []
    rules = load_rules()
    used = LimitsUsed(**(limits_used or {}))
    out: list[Obligation] = []
    for row in rules.kinds_mentioned(text):
        if row.category == ActivityCategory.JOB_SEARCH:
            continue
        verdict = admission(row.kind, group, round_no, used) if round_no else None
        if verdict and verdict.status == ActivityStatus.NOT_ALLOWED:
            out.append(Obligation(f"kind:{row.kind}", verdict.message or "", _NOT_ALLOWED_TOKENS,
                                  verdict.rule_refs))  # fmt: skip
            continue
        if round_no is None and (not row.allowed or (row.groups and group not in row.groups)):
            text_ = NOT_ALLOWED_TEXT.format(label=topic(row.label))
            out.append(Obligation(f"kind:{row.kind}", text_, _NOT_ALLOWED_TOKENS, row.rule_refs))
            continue
        if row.limit_group and (limit := rules.limit(row.limit_group)):
            times = (f"{limit.max}번", f"{limit.max}회", _SPOKEN_TIMES.get(limit.max, ""))
            out.append(
                Obligation(
                    f"limit:{limit.group}",
                    LIMIT_TEXT.format(label=topic(limit.label), max=limit.max),
                    (tuple(t for t in times if t),),
                    limit.rule_refs,
                )
            )
        if row.by_hours:
            hours = rules.training_hours
            out.append(
                Obligation(
                    f"hours:{row.kind}",
                    HOURS_TEXT.format(
                        label=topic(row.label), min=hours.min_counted, full=hours.full_round
                    ),
                    ((f"{hours.min_counted}시간",),),
                    hours.rule_refs,
                )
            )
    return out
