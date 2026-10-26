"""검색만 따로 재는 평가(LLM 답변 없음). 질문마다 정답 카드·청크가 몇 등에 오는지 봅니다.

질문 세트
- 규칙 카드: evals/retrieval/rule_queries.jsonl (저장소에 있음). style이 explicit(행정 용어)·
  colloquial(구어)·negative(관련 규칙 없음, 거절해야 함)
- 골든셋 카드: evals/golden/golden_set.csv에서 근거 칸에 규칙 카드 ID가 적힌 문항(마지막 말로 찾음).
  고용 형태만 다르고 내용이 같은 카드도 정답으로 봅니다. 영역(근거·절차·서류)별로도 냅니다.
- 정책·FAQ: data/knowledge/eval/*.jsonl (저장소에 없음). 사람 질문 41개, LLM 생성 80개.
  파일이 없으면 건너뜁니다.

지표
- hit@k: 정답 중 하나라도 k등 안에 있는 질문 비율. 대화에는 3장을 붙이므로 hit@3이 기준입니다.
- MRR@10: 첫 정답 등수의 역수 평균(10등 밖은 0).
- 거절 임계값: 코사인 유사도가 t 이상인 결과만 남길 때 정답 hit@3과 관련 없는 질문에 무엇이라도
  붙는 비율(오첨부)을 t별로 봅니다.

실행: backend/에서 `uv run python -m evals.retrieval.run` (색인을 먼저 채움: scripts.ingest.index)
"""

import argparse
import csv
import json
import re
import uuid
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.agent import gateway
from app.agent.retrieval import rewrite_query
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.repositories import knowledge as knowledge_repo
from app.rules.rule_cards import Profile, RuleCard, cards_by_id, cards_for
from app.schemas.knowledge import KnowledgeHit, KnowledgeKind
from app.services.knowledge import (
    GUIDE_KINDS,
    OTHER_EMPLOYMENT_TYPES,
    RULE_ID_PREFIX,
    SearchOptions,
    search,
)
from evals.golden.schema import CSV_PATH, TURN_SEP, split_list

HERE = Path(__file__).parent
REPORT_DIR = HERE.parent / "reports"
RULE_QUERIES = HERE / "rule_queries.jsonl"
KNOWLEDGE_EVAL = HERE.parents[1] / "data" / "knowledge" / "eval"
GUIDE_SETS = {
    "정책·FAQ 사람": ("queries_golden.jsonl", "queries_human.jsonl"),
    "정책·FAQ 생성": ("queries.jsonl",),
}
TOP = 10
ATTACH = 3  # 대화에 붙이는 수(INJECT_LIMIT)
THRESHOLDS = [round(0.30 + 0.05 * i, 2) for i in range(9)]
WORKERS = 8
GOLDEN_SET = "골든셋 카드"
RULE_ID = re.compile(r"\b(?:PROC|ELIG|ACT|DUE|SUP)-\d+\b")

# 이름 → (검색 조합, 질의 재작성, 사용자 조건 쓰기)
# 사용자 조건(수급자 유형·회차)은 profile 칸이 있는 질문에만 있습니다.
CONFIGS: dict[str, tuple[SearchOptions, bool, bool]] = {
    "bm25": (SearchOptions(vector=False), False, False),
    "vector": (SearchOptions(bm25=False), False, False),
    "hybrid": (SearchOptions(), False, False),
    "hybrid+syn": (SearchOptions(synonyms=True), False, False),
    "hybrid+rewrite": (SearchOptions(), True, False),
    "hybrid+syn+rewrite": (SearchOptions(synonyms=True), True, False),
    "hybrid+syn+filter": (SearchOptions(synonyms=True, profile_query=False), False, True),
    "hybrid+syn+profile": (SearchOptions(synonyms=True), False, True),
}


@dataclass
class Query:
    qid: str
    question: str
    positives: set[str]
    group: str  # rule | guide
    style: str
    profile: Profile | None = None
    area: str = ""  # 골든셋 영역(근거·절차·서류)


@dataclass
class Ranked:
    query: Query
    ids: list[str]
    sims: list[float | None]

    def rank(self) -> int | None:
        return next((i for i, c in enumerate(self.ids, 1) if c in self.query.positives), None)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def golden_queries() -> list[Query]:
    """골든셋 문항 중 근거 칸에 규칙 카드 ID가 적힌 것. 대화처럼 마지막 말로 찾습니다.

    골든셋 정답 카드가 3장 안에 붙는지를 LLM 없이 봅니다. 규칙표에 없는 ID는 뺍니다.
    """
    known = cards_by_id()
    # 고용 형태만 다르고 내용이 같은 카드(PROC-011 상용직 · PROC-027 노무제공자)는 같은 정답입니다.
    same_body: dict[str, set[str]] = {}
    for card in known.values():
        same_body.setdefault(card.body, set()).add(card.rule_id)
    with CSV_PATH.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    queries = []
    for row in rows:
        ids = [i for i in RULE_ID.findall(row["근거"]) if i in known]
        positives = {RULE_ID_PREFIX + j for i in ids for j in same_body[known[i].body]}
        if not positives:
            continue
        last = split_list(row["입력"], TURN_SEP)[-1]
        queries.append(Query(row["ID"], last, positives, "rule", row["방법"], area=row["영역"]))
    return queries


def load_queries() -> dict[str, list[Query]]:
    sets = {
        "규칙 카드": [
            Query(
                r["qid"],
                r["question"],
                {RULE_ID_PREFIX + p for p in r["positives"]},
                "rule",
                r["style"],
                Profile(**r["profile"]) if r.get("profile") else None,
            )  # fmt: skip
            for r in _jsonl(RULE_QUERIES)
        ]
    }
    sets[GOLDEN_SET] = golden_queries()
    if not KNOWLEDGE_EVAL.exists():
        return sets
    with SessionLocal() as db:
        allowed = {
            c.chunk_id
            for c in knowledge_repo.list_kinds(db, GUIDE_KINDS)
            if c.meta.get("employment_type") not in OTHER_EMPLOYMENT_TYPES
        }
    for name, files in GUIDE_SETS.items():
        queries = []
        for filename in files:
            for r in _jsonl(KNOWLEDGE_EVAL / filename):
                # 다른 고용 형태 전용 청크는 찾지 않으므로 그런 정답만 있는 질문은 뺍니다.
                positives = set(r["positives"]) & allowed
                if positives:
                    queries.append(Query(r["qid"], r["question"], positives, "guide", "human"))
        sets[name] = queries
    return sets


def _rewrites(questions: Iterable[str]) -> dict[str, str]:
    """재작성은 모델 호출이라 결과를 파일에 두고 다시 씁니다(재실행 비용·흔들림 줄이기)."""
    path = REPORT_DIR / "cache" / f"rewrite-{get_settings().extract_model}.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    todo = [q for q in dict.fromkeys(questions) if q not in cache]
    with ThreadPoolExecutor(WORKERS) as pool:
        cache |= dict(zip(todo, pool.map(rewrite_query, todo), strict=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


def _vectors(texts: Iterable[str]) -> dict[str, list[float]]:
    """질문 벡터도 파일에 둡니다. 질문용 모델이 바뀌면 파일 이름이 달라져 새로 만듭니다."""
    path = REPORT_DIR / "cache" / f"qvec-{get_settings().embedding_query_model}.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    todo = [t for t in dict.fromkeys(texts) if t not in cache]
    if todo:
        cache |= dict(zip(todo, gateway.embed_queries(todo), strict=True))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache), encoding="utf-8")
    return cache


def _fixed_hits(cards: list[RuleCard]) -> list[KnowledgeHit]:
    """정해진 카드를 검색 결과 모양으로(유사도는 1로 두어 임계값에 걸리지 않게)."""
    return [
        KnowledgeHit(
            RULE_ID_PREFIX + c.rule_id,
            KnowledgeKind.RULE_CARD,
            c.name,
            c.body,
            {"rule_id": c.rule_id},
            1.0,
        )  # fmt: skip
        for c in cards
    ]


def _with_fixed(hits: list[KnowledgeHit], fixed: list[RuleCard]) -> list[KnowledgeHit]:
    """대화(attach_knowledge)처럼 유형·회차에 정해진 카드를 검색 결과 앞에 둡니다."""
    fixed_ids = {c.rule_id for c in fixed}
    return _fixed_hits(fixed) + [h for h in hits if h.meta.get("rule_id") not in fixed_ids]


def run(configs: list[str]) -> dict[str, Any]:
    sets = load_queries()
    all_queries = [q for qs in sets.values() for q in qs]
    rewrites = (
        _rewrites(q.question for q in all_queries) if any(CONFIGS[c][1] for c in configs) else {}
    )
    texts = [q.question for q in all_queries] + list(rewrites.values())
    vectors = _vectors(texts)
    results: dict[str, dict[str, list[Ranked]]] = {}
    with SessionLocal() as db:
        for name in configs:
            options, rewrite, use_profile = CONFIGS[name]
            results[name] = {}
            for set_name, queries in sets.items():
                ranked = []
                for q in queries:
                    text = rewrites[q.question] if rewrite else q.question
                    found = search(
                        db, text, rule_limit=TOP if q.group == "rule" else 0,
                        guide_limit=TOP if q.group == "guide" else 0, options=options,
                        query_vector=vectors[text], profile=q.profile if use_profile else None,
                    )  # fmt: skip
                    hits = found.rules if q.group == "rule" else found.guides
                    if use_profile and q.profile and q.group == "rule":
                        hits = _with_fixed(hits, cards_for(q.profile.for_query(text)))
                    ranked.append(
                        Ranked(q, [h.chunk_id for h in hits], [h.similarity for h in hits])
                    )
                results[name][set_name] = ranked
    return {"sets": sets, "results": results, "rewrites": rewrites}


# ── 지표 ─────────────────────────────────────────────────


def metrics(ranked: list[Ranked]) -> dict[str, float | int]:
    positives = [r for r in ranked if r.query.positives]
    n = len(positives)
    if not n:
        return {"n": 0}
    ranks = [r.rank() for r in positives]
    return {
        "n": n,
        "hit@1": sum(1 for k in ranks if k and k <= 1) / n,
        "hit@3": sum(1 for k in ranks if k and k <= 3) / n,
        "hit@5": sum(1 for k in ranks if k and k <= 5) / n,
        "mrr@10": sum(1 / k for k in ranks if k) / n,
    }


def threshold_table(ranked: list[Ranked]) -> list[dict[str, float]]:
    """t별 정답 hit@3(임계값을 넘은 결과만)과 관련 없는 질문의 오첨부율."""
    rows = []
    positives = [r for r in ranked if r.query.positives]
    negatives = [r for r in ranked if not r.query.positives]
    for t in THRESHOLDS:

        def kept(r: Ranked, t: float = t) -> list[str]:
            return [
                c for c, s in zip(r.ids[:ATTACH], r.sims[:ATTACH], strict=True) if (s or 0) >= t
            ]

        hit = sum(1 for r in positives if set(kept(r)) & r.query.positives) / max(len(positives), 1)
        false_attach = sum(1 for r in negatives if kept(r)) / max(len(negatives), 1)
        avg_attached = sum(len(kept(r)) for r in positives) / max(len(positives), 1)
        rows.append({"t": t, "hit@3": hit, "false_attach": false_attach, "attached": avg_attached})
    return rows


def _fmt(value: float | int) -> str:
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def render(out: dict[str, Any], threshold_config: str | None) -> str:
    results = out["results"]
    lines = [f"# 검색 평가 ({datetime.now():%Y-%m-%d %H:%M})", ""]
    keys = ["n", "hit@1", "hit@3", "hit@5", "mrr@10"]
    for set_name in out["sets"]:
        lines += [f"## {set_name}", "", "| 방식 | " + " | ".join(keys) + " |",
                  "| --- " * (len(keys) + 1) + "|"]  # fmt: skip
        for name, by_set in results.items():
            m = metrics(by_set[set_name])
            lines.append(f"| {name} | " + " | ".join(_fmt(m.get(k, 0)) for k in keys) + " |")
        lines.append("")
    rule_sets = {name: by_set["규칙 카드"] for name, by_set in results.items()}
    for style in ("explicit", "colloquial", "profile"):
        lines += [f"## 규칙 카드 · {style}", "", "| 방식 | " + " | ".join(keys) + " |",
                  "| --- " * (len(keys) + 1) + "|"]  # fmt: skip
        for name, ranked in rule_sets.items():
            m = metrics([r for r in ranked if r.query.style == style])
            lines.append(f"| {name} | " + " | ".join(_fmt(m.get(k, 0)) for k in keys) + " |")
        lines.append("")
    golden_sets = {name: by_set[GOLDEN_SET] for name, by_set in results.items()}
    for area in ("근거", "절차", "서류"):
        lines += [f"## {GOLDEN_SET} · {area}", "", "| 방식 | " + " | ".join(keys) + " |",
                  "| --- " * (len(keys) + 1) + "|"]  # fmt: skip
        for name, ranked in golden_sets.items():
            m = metrics([r for r in ranked if r.query.area == area])
            lines.append(f"| {name} | " + " | ".join(_fmt(m.get(k, 0)) for k in keys) + " |")
        lines.append("")
    if threshold_config:
        lines += [f"## 거절 임계값 ({threshold_config}, 규칙 카드 상위 {ATTACH}장)", "",
                  "| t | 정답 hit@3 | 오첨부율 | 질문당 붙는 수 |",
                  "| --- | --- | --- | --- |"]  # fmt: skip
        for row in threshold_table(rule_sets[threshold_config]):
            lines.append(
                f"| {row['t']:.2f} | {row['hit@3']:.2f} | {row['false_attach']:.2f} "
                f"| {row['attached']:.2f} |"
            )
        lines.append("")
    return "\n".join(lines)


def misses(out: dict[str, Any], config: str) -> list[dict[str, Any]]:
    """3등 안에 정답이 없는 규칙 카드 질문(실패 분석용). 골든셋 문항도 함께 봅니다."""
    rows = []
    by_set = out["results"][config]
    for r in by_set["규칙 카드"] + by_set[GOLDEN_SET]:
        if r.query.positives and not (r.rank() or 99) <= ATTACH:
            rows.append({"qid": r.query.qid, "question": r.query.question, "rank": r.rank(),
                         "top3": r.ids[:ATTACH]})  # fmt: skip
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs", default=",".join(CONFIGS))
    parser.add_argument("--threshold-config", default="hybrid+syn")
    args = parser.parse_args()
    configs = args.configs.split(",")
    out = run(configs)
    threshold_config = args.threshold_config if args.threshold_config in configs else None
    text = render(out, threshold_config)
    REPORT_DIR.mkdir(exist_ok=True)
    stem = f"retrieval-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    (REPORT_DIR / f"{stem}.md").write_text(text, encoding="utf-8")
    detail = {name: misses(out, name) for name in configs}
    (REPORT_DIR / f"{stem}.json").write_text(
        json.dumps({"misses": detail, "rewrites": out["rewrites"]}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(text)
    print(f"→ {REPORT_DIR / stem}.md")


if __name__ == "__main__":
    main()
