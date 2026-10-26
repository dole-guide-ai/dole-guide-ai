"""'전체 순서가 궁금해요' 고정 안내 (F-05, 상세기획 1.6). LLM을 쓰지 않습니다."""

from typing import Any

OVERVIEW = (
    "실업급여는 네 단계로 진행돼요. ① 구직등록(이력서) ② 수급자격 신청자 온라인 교육 "
    "③ 고용센터에 수급자격 신청 ④ 4주마다 실업인정 신청이에요. 지금 단계부터 같이 해요."
)
# 네 단계의 근거 규칙 카드(구직신청·신청자 교육·센터 방문 신청·실업인정 신청)
OVERVIEW_RULE_REFS = ("PROC-009", "PROC-010", "PROC-011", "PROC-013")
# 답에 이 말이 절반 넘게 나오면 순서를 설명한 답으로 보고 근거 줄에 넣습니다(nodes/finish).
OVERVIEW_TERMS = "구직등록 온라인 교육 수급자격 신청 실업인정"


def overview() -> dict[str, Any]:
    return {"text": OVERVIEW, "rule_refs": list(OVERVIEW_RULE_REFS)}
