"""RAG 검색 지식의 종류와 검색 결과."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class KnowledgeKind(StrEnum):
    """검색 색인(knowledge_chunks)에 든 지식 종류. 규칙 카드를 먼저 씁니다."""

    RULE_CARD = "rule_card"  # 팀 규칙표 한 행 (data/rules/rule_table)
    FAQ = "faq"  # 고용노동부 1350 FAQ 질의·답변
    POLICY = "policy"  # 고용24 정책 안내(목록 요약·본문 조각)


@dataclass(frozen=True)
class KnowledgeHit:
    """검색 결과 한 건. similarity는 벡터 검색에 잡혔을 때의 코사인 유사도(거절 임계값에 씀)."""

    chunk_id: str
    kind: KnowledgeKind
    title: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)
    similarity: float | None = None
