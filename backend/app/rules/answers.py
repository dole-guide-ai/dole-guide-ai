"""신청서 본인 답변 규칙 (F-24·F-25, 설계 6.7·6.8). DB와 HTTP를 모르는 순수 함수입니다.

- 칸마다 받을 수 있는 값(선택지)과, 다른 답에 따라 묻는 칸(실업크레딧 세부는 `wish`일 때만,
  취업 시작일은 `none`이 아닐 때만)
- 만 60세 이상은 실업크레딧 `해당 없음`
- 취업·산재로 잠긴 신청서는 취업·산재 답만 고칠 수 있음
- "잘 모르겠어요"가 두 번이면 `conflict`(확인 필요)로 두고 제출을 막음
- 담당자 칸은 부서명만. 사람 이름은 저장하지 않음 (2-0.5)
"""

import re
from typing import Any

CREDIT_MIN_AGE = 60  # 만 60세 이상은 실업크레딧 대상이 아님 (설계 6.7)
NOT_APPLICABLE = "not_applicable"
WISH = "wish"
NONE = "none"

# 선택지가 정해진 칸 (설계 6.8)
CHOICES: dict[str, tuple[str, ...]] = {
    "/work/has_work": ("yes", "no"),
    "/employment/status": (NONE, "employed", "self_employed"),
    "/industrial_accident/receiving": ("yes", "no"),
    "/credit/application": (WISH, "not_wish", NOT_APPLICABLE),
    "/credit/notice_method": ("electronic", "mail"),
    "/credit/auto_payment": (WISH, "not_wish"),
    "/credit/income_asset_consent": ("agree", "disagree"),
    "/notification_method": ("sms", "email", "mail"),
    "/privacy_consent": ("agree_all", "agree_required_only", "disagree"),
}
DATE_PATHS = ("/employment/started_on",)
LIST_PATHS = ("/work/entries", "/next_plan")
# 실업크레딧을 희망할 때만 묻는 칸
CREDIT_DETAIL_PATHS = (
    "/credit/notice_method",
    "/credit/auto_payment",
    "/credit/income_asset_consent",
)
# 잠긴 신청서에서도 고칠 수 있는 칸 (잘못 답했으면 바로잡을 수 있게)
LOCK_PATHS = ("/employment/status", "/employment/started_on", "/industrial_accident/receiving")

# 담당자 칸에 들어온 사람 호칭 ("김OO 과장님", "이 대리")
_TITLES = "과장|대리|부장|차장|팀장|실장|주임|사원|이사|대표|매니저|선생|담당자"
_PERSON = re.compile(rf"^[가-힣OoＯ○*]{{1,4}}\s*(({_TITLES})\s*님?|님)$")
_TITLE_TAIL = re.compile(rf"\s*[가-힣OoＯ○*]{{1,4}}\s*({_TITLES})\s*님?$")


def _value(data: dict[str, Any], path: str) -> Any:
    node: Any = data
    for key in path.strip("/").split("/"):
        node = node.get(key) if isinstance(node, dict) else None
    return node.get("value") if isinstance(node, dict) else None


def credit_applicable(age: int) -> bool:
    return age < CREDIT_MIN_AGE


def answer_error(path: str, value: Any, data: dict[str, Any], age: int) -> str | None:
    """받을 수 없는 답이면 이유(PatchErrorType 값), 받을 수 있으면 None.

    `value`가 None이면 지우기라 값 검사는 하지 않습니다.
    """
    if value is None:
        return None
    if choices := CHOICES.get(path):
        if value not in choices:
            return "choice"
        if path == "/credit/application" and (value == NOT_APPLICABLE) == credit_applicable(age):
            # 60세 미만은 해당 없음을 고를 수 없고, 60세 이상은 희망·비희망을 고를 수 없습니다.
            return "choice"
    if path in CREDIT_DETAIL_PATHS and _value(data, "/credit/application") != WISH:
        return "required"
    if path in DATE_PATHS:
        if _value(data, "/employment/status") in (None, NONE):
            return "required"
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value, re.ASCII):
            return "date_format"
    if path in LIST_PATHS and not (
        isinstance(value, list) and all(isinstance(item, dict) for item in value)
    ):
        return "bad_shape"
    return None


def blocked_by_lock(path: str, locked: str | None) -> bool:
    return locked is not None and path not in LOCK_PATHS


def conflict_paths(data: dict[str, Any], prefix: str = "") -> list[str]:
    """확인 필요(`conflict`)로 남은 칸. "잘 모르겠어요"를 두 번 해서 비운 답입니다."""
    found: list[str] = []
    for key, node in data.items():
        if not isinstance(node, dict):
            continue
        path = f"{prefix}/{key}"
        if "value" in node and "status" in node:
            if node.get("status") == "conflict":
                found.append(path)
        else:
            found += conflict_paths(node, path)
    return found


def department_only(text: str | None) -> str | None:
    """담당자 칸에서 사람 이름·호칭을 뺍니다 (F-25: "김OO 과장님"은 저장하지 않음).

    "인사팀 김OO 과장님"이면 "인사팀"만, 이름·호칭뿐이면 None입니다.
    """
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned or _PERSON.fullmatch(cleaned):
        return None
    dept = _TITLE_TAIL.sub("", cleaned).strip()
    return dept or None
