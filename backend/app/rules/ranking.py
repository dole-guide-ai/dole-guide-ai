"""검색 순위 부품: 글자 두 개 묶음 BM25와 순위 합치기(RRF). LLM·DB 없음.

- BM25: 질문과 같은 글자 묶음이 많고, 그 묶음이 흔하지 않을수록 점수가 높습니다(단어 검색).
- RRF: 여러 검색 결과를 점수가 아니라 등수로 합칩니다. BM25 점수와 코사인 유사도는 단위가 달라
  더할 수 없지만, 등수는 같은 단위입니다. 두 방식 모두 위에 올린 문서가 위로 갑니다.
"""

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

BM25_K1 = 1.2
BM25_B = 0.75
# RRF 상수. 원 논문(Cormack 2009)과 대부분의 검색 엔진 기본값입니다.
RRF_K = 60


def bigrams(text: str) -> list[str]:
    """한국어는 띄어쓰기·조사가 들쭉날쭉해서 글자 두 개씩 묶어 비교합니다(형태소 분석기 없이)."""
    grams: list[str] = []
    for word in re.findall(r"[0-9A-Za-z가-힣]+", text.lower()):
        if len(word) > 1:
            grams.extend(word[i : i + 2] for i in range(len(word) - 1))
        else:
            grams.append(word)
    return grams


class Bm25Index:
    """문서마다 칸별 가중치를 곱해 센 글자 묶음으로 BM25 점수를 매깁니다."""

    def __init__(
        self, docs: Iterable[tuple[str, Mapping[str, str]]], weights: Mapping[str, int]
    ) -> None:
        self._terms: list[tuple[str, Counter[str], int]] = []
        for doc_id, fields in docs:
            terms: Counter[str] = Counter()
            for name, weight in weights.items():
                for gram in bigrams(fields.get(name, "")):
                    terms[gram] += weight
            self._terms.append((doc_id, terms, sum(terms.values())))
        self._doc_freq = Counter(g for _, terms, _ in self._terms for g in terms)
        self._avg_len = sum(n for *_, n in self._terms) / len(self._terms) if self._terms else 0

    def search(self, query: str, limit: int) -> list[tuple[str, float]]:
        """점수 높은 순. 겹치는 글자 묶음이 없는 문서는 빼므로 결과가 limit보다 적을 수 있습니다."""
        grams = set(bigrams(query))
        total = len(self._terms)
        scored = []
        for doc_id, terms, length in self._terms:
            score = 0.0
            for gram in grams & terms.keys():
                df = self._doc_freq[gram]
                idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
                tf = terms[gram]
                norm = tf + BM25_K1 * (1 - BM25_B + BM25_B * length / self._avg_len)
                score += idf * tf * (BM25_K1 + 1) / norm
            if score > 0:
                scored.append((doc_id, score))
        scored.sort(key=lambda pair: -pair[1])
        return scored[:limit]


def rrf(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """등수로 합칩니다: 점수 = Σ 1 / (k + 등수). 한쪽에만 있어도 들어갑니다."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda pair: -pair[1])
