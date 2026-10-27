"""골든셋 CSV 한 줄을 시나리오(dict)로 바꾸는 규칙. 열 설명은 evals/README.md의 '골든셋' 절."""

import re
from pathlib import Path
from typing import Any

from app.rules.next_action import NextAction

GOLDEN_DIR = Path(__file__).parent
CSV_PATH = GOLDEN_DIR / "golden_set.csv"
FILES_DIR = GOLDEN_DIR / "files"
OUT_DIR = GOLDEN_DIR.parent / "scenarios" / "golden"

COLUMNS = [
    "ID", "영역", "방법", "검수", "세트", "설명", "계정", "상태값", "활동", "입력", "첨부",
    "다음할일", "기대값", "변경금지", "꼭포함", "포함금지", "금지패턴", "개인정보검사",
    "근거표시", "채점기준", "근거",
]  # fmt: skip
REQUIRED = ["ID", "영역", "방법", "검수", "세트", "설명", "계정", "입력"]
AREAS = {"절차": "procedure", "서류": "form_fill", "근거": "grounding", "개인정보": "masking"}
METHODS = {"기본", "경계값", "바꿔말하기", "여러턴", "공격", "범위밖", "회귀", "파일"}
REVIEWS = {"확정", "확인필요", "보류"}
# 개발용: 프롬프트·규칙을 고칠 때 보고 돌리는 문항.
# 검증용: 최종 확인 때만 돌리고, 보고 고치지 않는 문항.
SETS = {"개발": "dev", "검증": "test"}
# 다음할일 값은 에이전트가 done 이벤트에 싣는 값(rules/next_action.NextAction)과 같습니다.
NEXT_ACTIONS = {action.value for action in NextAction}
PRIVACY_SCOPES = {"전체": "all", "답": "reply", "저장": "stored", "모델": "model"}
ROUTES = {
    "work24", "portal", "email", "company_site", "newspaper", "mail", "fax", "visit", "referral",
    "interview", "job_fair", "training", "center", "step_online",
}  # fmt: skip
# 기대값 한 칸: 경로 연산자 값. = 같음, != 다름, ^= 로 시작, *= 포함(글자·목록)
EXPECT = re.compile(r"^(?P<path>[\w.\[\]-]+?)\s*(?P<op>\^=|\*=|!=|=)\s*(?P<value>.*)$")
OPS = {"=": "eq", "!=": "ne", "^=": "prefix", "*=": "contains"}
TURN_SEP = "||"


class GoldenError(ValueError):
    """CSV 내용 오류. 메시지는 사람이 바로 고칠 수 있게 씁니다."""


def split_list(cell: str, sep: str = ";") -> list[str]:
    return [part.strip() for part in (cell or "").split(sep) if part.strip()]


def parse_value(text: str) -> Any:
    """'true'·'false'·'null'·'[]'·숫자는 그 값으로, 나머지는 글자 그대로."""
    raw = text.strip()
    special = {"true": True, "false": False, "null": None, "[]": []}
    if raw in special:
        return special[raw]
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def parse_pairs(cell: str, column: str) -> dict[str, Any]:
    pairs = {}
    for part in split_list(cell):
        key, sep, value = part.partition("=")
        if not sep or not key.strip():
            raise GoldenError(f"{column} '{part}'은 '이름=값' 모양이어야 해요.")
        pairs[key.strip()] = parse_value(value)
    return pairs


def parse_expect(cell: str) -> list[dict[str, Any]]:
    checks = []
    for part in split_list(cell):
        match = EXPECT.match(part)
        if not match:
            raise GoldenError(f"기대값 '{part}'은 '경로=값'(또는 !=, ^=, *=) 모양이어야 해요.")
        op = OPS[match["op"]]
        value = (
            match["value"].strip() if op in ("prefix", "contains") else parse_value(match["value"])
        )
        checks.append({"path": match["path"], "op": op, "value": value})
    return checks


def parse_activities(cell: str) -> list[dict[str, Any]] | None:
    """'날짜 종류 경로 [기관]; ...' → 활동 목록. 비우면 None(계정 기본값), '없음'이면 빈 목록."""
    if not (cell or "").strip():
        return None
    if cell.strip() == "없음":
        return []
    activities = []
    for part in split_list(cell):
        tokens = part.split(maxsplit=3)
        date, kind, route, *org = tokens if len(tokens) >= 3 else ("", "", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or kind not in ("job_search", "other"):
            raise GoldenError(
                f"활동 '{part}'은 '2026-12-08 job_search work24 OO물류' 모양이어야 해요."
            )
        if route not in ROUTES:
            raise GoldenError(f"활동 경로 '{route}'를 모르겠어요. 쓸 수 있는 값: {sorted(ROUTES)}")
        activities.append({"date": date, "kind": kind, "route": route, "org_name": " ".join(org)})
    return activities


def parse_privacy(cell: str) -> list[dict[str, str]]:
    """'저장:디스크; 모델:홍길동; 800101-1234567' → 범위별 금지 글자. 범위를 빼면 전체."""
    items = []
    for part in split_list(cell):
        scope, sep, text = part.partition(":")
        if sep and scope.strip() in PRIVACY_SCOPES:
            items.append({"scope": PRIVACY_SCOPES[scope.strip()], "text": text.strip()})
        else:
            items.append({"scope": "all", "text": part})
    return items


def row_to_case(row: dict[str, str]) -> dict[str, Any]:
    """CSV 한 줄 → 시나리오. 계정 기본값은 build 단계에서 합칩니다."""
    cell = {name: (row.get(name) or "").strip() for name in COLUMNS}
    if missing := [name for name in REQUIRED if not cell[name]]:
        raise GoldenError(f"꼭 채워야 하는 칸이 비었어요: {', '.join(missing)}")
    checks = {"영역": AREAS, "방법": METHODS, "검수": REVIEWS, "세트": SETS}
    for name, allowed in checks.items():
        if cell[name] not in allowed:
            raise GoldenError(
                f"{name} '{cell[name]}'은 다음 중 하나여야 해요: {', '.join(allowed)}"
            )
    if cell["다음할일"] and cell["다음할일"] not in NEXT_ACTIONS:
        raise GoldenError(f"다음할일 '{cell['다음할일']}'은 목록에 없어요: {sorted(NEXT_ACTIONS)}")
    if cell["근거표시"] not in ("", "Y", "N"):
        raise GoldenError("근거표시는 Y, N 중 하나이거나 비워야 해요.")
    for pattern in split_list(cell["금지패턴"]):
        try:
            re.compile(pattern)
        except re.error as error:
            raise GoldenError(f"금지패턴 '{pattern}'이 정규식으로 맞지 않아요: {error}") from error
    expected = {
        "next_action": cell["다음할일"] or None,
        "values": parse_expect(cell["기대값"]),
        "unchanged": split_list(cell["변경금지"]),
        "must_include": split_list(cell["꼭포함"]),
        "must_not_include": split_list(cell["포함금지"]),
        "forbidden_patterns": split_list(cell["금지패턴"]),
        "privacy": parse_privacy(cell["개인정보검사"]),
        "cite_required": cell["근거표시"] == "Y",
        # 채점기준은 ';'로 여러 기준을 적을 수 있고, 기준마다 따로 판정합니다(#261).
        "judge": split_list(cell["채점기준"]) or None,
    }
    if not any(expected.values()):
        raise GoldenError(
            "채점할 기대 결과가 하나도 없어요. 기대값·꼭포함·채점기준 중 하나는 채워 주세요."
        )
    return {
        "id": cell["ID"],
        "area": AREAS[cell["영역"]],
        "method": cell["방법"],
        "review": cell["검수"],
        "set": SETS[cell["세트"]],
        "description": cell["설명"],
        "source": cell["근거"],
        "input": {
            "persona": cell["계정"],
            "state": parse_pairs(cell["상태값"], "상태값"),
            "activities": parse_activities(cell["활동"]),
            "messages": split_list(cell["입력"], TURN_SEP),
            "files": split_list(cell["첨부"]),
        },
        "expected": expected,
    }
