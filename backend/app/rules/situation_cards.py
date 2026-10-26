"""활동 규칙 표를 내 상황(수급자 유형·회차)에 맞춘 '상황 카드' 문장으로 바꿉니다.

검색(RAG) 대신, 정리된 규칙 표(data/rules/activities.json, 약 5KB)를 통째로 문장으로 넣는
대안입니다. 인정 여부는 회차 점검과 같은 함수(`rounds.is_not_allowed`)로 정해, 대화와 계산이
어긋나지 않게 합니다.
DB·LLM을 모르는 순수 함수입니다.
"""

from typing import Any

from app.rules.activity_table import load_rules
from app.rules.rounds import is_not_allowed

CITE = "2026 실업인정 인정기준 안내문(활동 규칙 표)"
# 경로(route) → 사용자에게 보이는 이름
ROUTE_LABELS = {
    "work24": "고용24(워크넷) 입사지원",
    "step_online": "온라인 취업특강(STEP)",
    "portal": "취업포털(사람인·잡코리아 등) 지원",
    "email": "이메일 지원",
    "company_site": "기업 홈페이지 지원",
    "newspaper": "신문 공고 지원",
    "interview": "면접",
    "referral": "소개로 본 면접",
    "job_fair": "채용박람회",
    "mail": "우편 지원",
    "fax": "팩스 지원",
    "training": "직업훈련",
}


def build_rule_cards(
    derived: dict[str, Any], *, include_evidence: bool = True
) -> list[dict[str, str]]:
    """이번 회차에 인정되는 활동·안 되는 활동·누적 한도·경로별 증빙 문장 [{text, cite}].

    경로별 증빙은 팀 규칙표 카드 검색과 겹치므로, 그래프 facts에 붙일 때는 뺍니다
    (include_evidence=False).
    """
    rules = load_rules()
    group, round_no = derived["group"], derived["current_round"] or 1
    allowed = [k.label for k in rules.kinds if not is_not_allowed(k, rules, group, round_no)]
    denied = [k.label for k in rules.kinds if is_not_allowed(k, rules, group, round_no)]
    cards = [
        f"이번 회차에 인정되는 활동: {', '.join(allowed)}.",
        f"이번 회차에 인정되지 않는 활동: {', '.join(denied)}.",
        "누적 한도(수급 기간 전체): "
        + ", ".join(f"{limit.label} {limit.max}회까지" for limit in rules.limits)
        + ".",
    ]
    training = next((k for k in rules.kinds if k.by_hours), None)
    if training and not is_not_allowed(training, rules, group, round_no):
        # 직업훈련이 인정되지 않는 회차(구직활동만 인정)에는 시간 기준을 말하지 않습니다.
        cards.append(
            f"직업훈련은 대상 기간에 {rules.training_hours.min_counted}시간 이상이면 1건, "
            f"{rules.training_hours.full_round}시간 이상이면 그 회차 활동을 모두 채운 것으로 봐요."
        )
    if include_evidence:
        for route in rules.routes:
            label = ROUTE_LABELS.get(route.route, route.route)
            evidence = ", ".join(route.evidence) if route.evidence else "따로 낼 증빙이 없어요"
            cards.append(f"{label}의 증빙: {evidence}.")
    return [{"text": text, "cite": CITE} for text in cards]
