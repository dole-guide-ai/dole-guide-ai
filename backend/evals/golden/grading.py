"""골든셋 채점: AI 결과(AgentResult)를 문항의 기대 결과와 비교해 틀린 이유 목록을 돌려줍니다.

LLM 판정(채점기준)은 judge.py가 따로 합니다. 여기는 정답 비교와 글자 검사만 합니다.
"""

import json
import re
from typing import TYPE_CHECKING, Any

from app.agent.output import FOREIGN_SCRIPT

if TYPE_CHECKING:
    from evals.golden.adapter import AgentResult

TOKEN = re.compile(r"([^.\[\]]+)|\[(-?\d+)\]")
MISSING = object()
# 꼭포함 칸에서 같은 뜻의 다른 표현을 나누는 글자("17시|17:00")
ALTERNATIVE = "|"


def _tokens(path: str) -> list[str | int]:
    return [int(index) if index else name for name, index in TOKEN.findall(path)]


def resolve(data: Any, path: str) -> Any:
    """'resume.competencies.careers[-1].start_date', 'activities.length' 같은 경로의 값.

    없으면 MISSING.
    """
    current = data
    for token in _tokens(path):
        if token == "length" and isinstance(current, list):
            return len(current)
        if (
            (
                isinstance(token, int)
                and isinstance(current, list)
                and -len(current) <= token < len(current)
            )
            or isinstance(token, str)
            and isinstance(current, dict)
            and token in current
        ):
            current = current[token]
        else:
            return MISSING
    return current


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    """자체 점검용: 경로에 값을 넣습니다. 중간이 없으면 만들고, '.length'면 목록 길이를 맞춥니다."""
    tokens = _tokens(path)
    current: Any = data
    for token, nxt in zip(tokens, [*tokens[1:], None], strict=True):
        if nxt == "length" and isinstance(token, str):
            items = current.setdefault(token, [])
            items[:] = (items + [{} for _ in range(value)])[:value]
            return
        if nxt is None:
            if isinstance(token, int):
                if not current:
                    current.append(None)
                current[token] = value
            else:
                current[token] = value
            return
        container: Any = [] if isinstance(nxt, int) else {}
        if isinstance(token, int):
            if not current:
                current.append(container)
            current = current[token]
        else:
            current = current.setdefault(token, container)


def _matches(op: str, actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "prefix":
        return isinstance(actual, str) and actual.startswith(expected)
    if isinstance(actual, list):
        return any(expected in str(item) for item in actual)
    return isinstance(actual, str) and expected in actual


def _show(value: Any) -> str:
    return "(없음)" if value is MISSING else json.dumps(value, ensure_ascii=False)


def check(case: dict[str, Any], result: AgentResult) -> list[str]:
    expected = case["expected"]
    initial = case["input"]["data"] if result.initial_data is None else result.initial_data
    failures = []
    if expected["next_action"] and result.next_action != expected["next_action"]:
        failures.append(f"다음할일: {result.next_action!r} (기대 {expected['next_action']!r})")
    for item in expected["values"]:
        actual = resolve(result.data, item["path"])
        if not _matches(item["op"], actual, item["value"]):
            sign = {"eq": "=", "ne": "!=", "prefix": "^=", "contains": "*="}[item["op"]]
            want = item["value"] if isinstance(item["value"], str) else _show(item["value"])
            failures.append(f"기대값 {item['path']}{sign}{want} 아님 (실제 {_show(actual)})")
    for path in expected["unchanged"]:
        if resolve(result.data, path) != resolve(initial, path):
            failures.append(f"변경금지: {path}이(가) 바뀜")
    last_reply = result.replies[-1] if result.replies else ""
    all_replies = "\n".join(result.replies)
    # 꼭포함 "A|B"는 같은 뜻의 다른 표현이라 하나만 있으면 됩니다("17시|17:00").
    failures += [f"꼭포함: '{word}'이(가) 답에 없음" for word in expected["must_include"]
                 if not any(alt in last_reply for alt in word.split(ALTERNATIVE))]  # fmt: skip
    failures += [f"포함금지: '{word}'이(가) 답에 있음" for word in expected["must_not_include"]
                 if word in all_replies]  # fmt: skip
    patterns = expected["forbidden_patterns"]
    failures += [f"금지패턴: /{pattern}/에 맞는 글이 답에 있음"
                 for pattern in patterns if re.search(pattern, all_replies)]  # fmt: skip
    # 모든 문항 공통: 다른 언어 문자가 답에 섞이면 출력 관문(agent/output.py)이 놓친 것입니다.
    if FOREIGN_SCRIPT.search(all_replies):
        failures.append("외국문자: 답에 다른 언어 문자가 섞임")
    if expected["cite_required"] and not result.cites:
        failures.append("근거표시: 답에 근거 줄이 없음")
    stored = "\n".join([*result.stored, json.dumps(result.data, ensure_ascii=False)])
    places = {"reply": all_replies, "stored": stored, "model": "\n".join(result.model_inputs)}
    names = {"reply": "답", "stored": "저장값", "model": "모델 입력"}
    for item in expected["privacy"]:
        scopes = list(places) if item["scope"] == "all" else [item["scope"]]
        shown = item["text"][:3] + "…"  # 보고서·로그에 전체 값을 남기지 않습니다.
        failures += [f"개인정보: '{shown}'이(가) {names[scope]}에 남음"
                     for scope in scopes if item["text"] in places[scope]]  # fmt: skip
    return failures
