"""processed JSON → 임베딩 직전 검색 청크(JSONL 3개). 임베딩 모델은 호출하지 않습니다.

Notion「OpenAPI, 크롤링 데이터 세부 설계」6절, 1350 FAQ 6절 기준:
- 정책 탐색용: 정책당 1개 (정책명·대상·분야·요약)
- 정책 본문: 목차 → 소제목 → 의미 단위 → 길이 순으로 경계를 정합니다.
  FAQ는 질문·답변 한 쌍, 신청절차는 단계 하나가 각각 청크 하나입니다.
  나머지는 목표 크기까지 합치고, 최대 크기를 넘으면 문단·문장·표 행 단위로 나눕니다.
- 1350 FAQ: FAQ 1건당 1개, 길면 질문을 유지한 채 답변을 나눕니다.
숫자·기간·자격요건·예외는 요약하거나 지우지 않고 원문 그대로 담습니다.

uv run python -m scripts.ingest.chunk
"""

import json
import re
from collections.abc import Iterable
from pathlib import Path

from scripts.ingest import paths
from scripts.ingest.fetch import save_text
from scripts.ingest.schemas import (
    Block,
    Chunk,
    FaqDetail,
    PolicyCatalogItem,
    PolicyDetail,
    PolicySection,
)

# 청크 크기(토큰). 임베딩 모델이 정해지지 않아 공백을 뺀 글자 수로 어림잡습니다.
# 한국어는 대부분의 토크나이저에서 글자당 1토큰 이하라 실제 토큰 수는 이보다 적거나 같습니다.
MIN_TOKENS = 300
TARGET_TOKENS = 600
MAX_TOKENS = 800

# 소제목으로 볼 짧은 번호 문단: "1) 서류 제출", "2. 구직 등록", "① 사전 교육"
_NUMBERED_TITLE = re.compile(r"^(\(?\d{1,2}[).]|[①-⑳])\s*\S")
_SUBTITLE_MAX_CHARS = 40
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

# 실업급여 고용형태별 정책명 → metadata.employment_type
EMPLOYMENT_TYPES = {
    "상용직": "regular",
    "일용직": "daily",
    "예술인": "artist",
    "노무제공자": "labor_provider",
    "자영업자": "self_employed",
}
# 변경 가능성이 큰 정보(금액·기간·자격)가 있으면 고용24와 대조가 필요하다고 표시합니다.
_VOLATILE = re.compile(r"\d|금액|기간|자격|기한|일수")


def estimate_tokens(text: str) -> int:
    return len("".join(text.split()))


def render_block(block: Block) -> str:
    """블록을 임베딩·LLM이 읽기 쉬운 텍스트(Markdown 형태)로 바꿉니다."""
    match block.type:
        case "list":
            return "\n".join(f"- {item}" for item in block.items)
        case "table":
            return render_table(block.rows)
        case "step":
            return f"{block.step_number}. {block.text}"
        case "faq":
            return f"질문: {block.question}\n답변: {block.answer}"
        case _:
            return block.text


def render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)

    def line(row: list[str]) -> str:
        cells = [cell.replace("\n", " ").replace("|", "/") for cell in row]
        return "| " + " | ".join(cells + [""] * (width - len(cells))) + " |"

    return "\n".join(
        [line(rows[0]), "| " + " | ".join(["---"] * width) + " |", *map(line, rows[1:])]
    )


def _is_subtitle(block: Block) -> bool:
    if block.type == "heading":
        return True
    return (
        block.type == "paragraph"
        and len(block.text) <= _SUBTITLE_MAX_CHARS
        and bool(_NUMBERED_TITLE.match(block.text))
    )


class _Unit:
    """청크 후보: 소제목 하나와 그 아래 블록들."""

    def __init__(self, kind: str, blocks: list[Block] | None = None) -> None:
        self.kind = kind  # section | step | faq
        self.blocks: list[Block] = blocks or []

    @property
    def title(self) -> str | None:
        first = self.blocks[0] if self.blocks else None
        return first.text if first is not None and _is_subtitle(first) else None

    def body(self) -> str:
        return "\n".join(render_block(b) for b in self.blocks)

    def tokens(self) -> int:
        return estimate_tokens(self.body())


def _units(section: PolicySection) -> list[_Unit]:
    units: list[_Unit] = []
    for block in section.blocks:
        if block.type == "faq":
            units.append(_Unit("faq", [block]))
        elif block.type == "step":
            # 절차 요약(가 → 나 → 다)의 단계들은 순서를 보존해 한 묶음으로 둡니다.
            if not units or units[-1].kind != "step" or units[-1].blocks[-1].type != "step":
                units.append(_Unit("step"))
            units[-1].blocks.append(block)
        elif _is_subtitle(block):
            kind = "step" if section.section_type == "procedure" else "section"
            units.append(_Unit(kind, [block]))
        else:
            if not units or units[-1].kind == "faq" or units[-1].blocks[-1].type == "step":
                units.append(_Unit("section"))
            units[-1].blocks.append(block)
    return units


def _merge_small(units: list[_Unit]) -> list[_Unit]:
    """짧은 일반 묶음은 목표 크기까지 이웃과 합칩니다. FAQ·단계는 하나씩 둡니다."""
    merged: list[_Unit] = []
    for unit in units:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and unit.kind == previous.kind == "section"
            and previous.tokens() < MIN_TOKENS
            and previous.tokens() + unit.tokens() <= TARGET_TOKENS
        ):
            previous.blocks += unit.blocks
        else:
            merged.append(unit)
    return merged


def _split_text(text: str, limit: int) -> list[str]:
    """줄 → 문장 경계에서 limit 이하로 나눕니다. 그래도 길면 글자 수로 자릅니다."""
    pieces = [s for line in text.split("\n") for s in _SENTENCE_END.split(line) if s.strip()]
    parts: list[str] = []
    current = ""
    for piece in pieces:
        while estimate_tokens(piece) > limit:
            parts += [current] if current else []
            current = ""
            cut = len(piece) * limit // max(1, estimate_tokens(piece))
            parts.append(piece[:cut])
            piece = piece[cut:]
        candidate = f"{current}\n{piece}" if current else piece
        if estimate_tokens(candidate) > limit:
            parts.append(current)
            current = piece
        else:
            current = candidate
    return [part for part in [*parts, current] if part.strip()]


def _split_block(block: Block, limit: int) -> list[str]:
    if block.type == "table" and len(block.rows) > 2:
        header, rows = block.rows[0], block.rows[1:]
        parts: list[list[list[str]]] = [[]]
        for row in rows:
            if parts[-1] and estimate_tokens(render_table([header, *parts[-1], row])) > limit:
                parts.append([])
            parts[-1].append(row)
        return [render_table([header, *part]) for part in parts]
    return _split_text(render_block(block), limit)


def _pack(unit: _Unit, limit: int) -> list[tuple[str, list[str]]]:
    """(본문, 블록 ID들) 목록. 넘치면 블록 경계에서, 블록 하나가 넘치면 그 안에서 나눕니다.
    나뉜 뒤쪽 조각에는 소제목을 다시 붙여 문맥을 잃지 않게 합니다."""
    if unit.tokens() <= limit:
        return [(unit.body(), [b.block_id for b in unit.blocks])]
    title = unit.title
    prefix = f"{title}\n" if title else ""
    parts: list[tuple[str, list[str]]] = []
    current, ids = "", []
    for block in unit.blocks:
        for piece in _split_block(block, limit - estimate_tokens(prefix)):
            candidate = f"{current}\n{piece}" if current else piece
            if current and estimate_tokens(candidate) > limit:
                parts.append((current, ids))
                current, ids = prefix + piece, []
            else:
                current = candidate
            if block.block_id not in ids:
                ids.append(block.block_id)
    if current:
        parts.append((current, ids))
    return parts


def _chunk_type(unit: _Unit) -> str:
    if unit.kind != "section":
        return unit.kind
    return "table" if all(b.type == "table" for b in unit.blocks) else "section"


def employment_type(title: str) -> str | None:
    if "실업급여" not in title:
        return None
    return next((value for key, value in EMPLOYMENT_TYPES.items() if key in title), None)


def policy_catalog_chunk(item: PolicyCatalogItem, detail: PolicyDetail) -> Chunk:
    sections = ", ".join(s.original_title for s in detail.sections if s.blocks)
    lines = [
        f"정책: {item.policy_name}",
        f"대상: {item.target_label}",
        f"분야: {item.category_label}",
        f"요약: {item.summary}",
        f"목차: {sections}",
    ]
    return Chunk(
        chunk_id=f"{item.key}_catalog",
        chunk_scope="catalog",
        chunk_type="catalog",
        policy_id=item.key,
        sequence=1,
        content="\n".join(line for line in lines if not line.endswith(": ")),
        metadata=_policy_metadata(item, detail),
    )


def _policy_metadata(item: PolicyCatalogItem, detail: PolicyDetail) -> dict:
    return {
        "source": "work24",
        "policy_name": item.policy_name,
        "source_url": item.detail_url,
        "last_modified": detail.last_modified,
        "employment_type": employment_type(item.policy_name),
        "priority": "primary",
    }


def policy_content_chunks(item: PolicyCatalogItem, detail: PolicyDetail) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in detail.sections:
        if not section.blocks:
            continue
        header = f"정책: {item.policy_name}\n목차: {section.original_title}\n"
        limit = MAX_TOKENS - estimate_tokens(header)
        sequence = 0
        for unit in _merge_small(_units(section)):
            chunk_type = _chunk_type(unit)
            for body, block_ids in _pack(unit, limit):
                sequence += 1
                chunks.append(
                    Chunk(
                        chunk_id=f"{section.section_id}_{chunk_type}{sequence:02}",
                        chunk_scope="content",
                        chunk_type=chunk_type,
                        policy_id=item.key,
                        section_id=section.section_id,
                        section_type=section.section_type,
                        sequence=sequence,
                        content=header + body,
                        block_ids=block_ids,
                        metadata={
                            **_policy_metadata(item, detail),
                            "original_title": section.original_title,
                        },
                    )
                )
    return chunks


def faq_chunks(faq: FaqDetail) -> list[Chunk]:
    header = f"제목: {faq.title}\n질의: {faq.question}\n답변: "
    limit = MAX_TOKENS - estimate_tokens(header)
    answers = (
        [faq.answer] if estimate_tokens(faq.answer) <= limit else _split_text(faq.answer, limit)
    )
    metadata = {
        "source": "moel_1350",
        "title": faq.title,
        "source_url": faq.source_url,
        "published_at": faq.published_at,
        "priority": "secondary",
        "requires_policy_verification": bool(_VOLATILE.search(faq.answer)),
    }
    return [
        Chunk(
            chunk_id=f"FAQ1350_{faq.faq_id}_{order:02}",
            chunk_scope="faq",
            chunk_type="faq_pair",
            faq_id=faq.faq_id,
            sequence=order,
            content=header + answer,
            metadata=metadata,
        )
        for order, answer in enumerate(answers, start=1)
    ]


def _write_jsonl(path: Path, chunks: Iterable[Chunk]) -> int:
    lines = [json.dumps(c.model_dump(), ensure_ascii=False) for c in chunks]
    save_text(path, "\n".join(lines) + "\n")
    return len(lines)


def main() -> None:
    catalog_path = paths.WORK24_PROCESSED / "policy_catalog.json"
    catalog = [
        PolicyCatalogItem.model_validate(item)
        for item in json.loads(catalog_path.read_text(encoding="utf-8"))
    ]
    catalog_chunks, content_chunks = [], []
    for item in catalog:
        detail_path = paths.WORK24_PROCESSED / "policies" / f"{item.key}.json"
        detail = PolicyDetail.model_validate_json(detail_path.read_text(encoding="utf-8"))
        catalog_chunks.append(policy_catalog_chunk(item, detail))
        content_chunks += policy_content_chunks(item, detail)

    faq_list: list[Chunk] = []
    for path in sorted((paths.FAQ_PROCESSED / "details").glob("*.json")):
        faq_list += faq_chunks(FaqDetail.model_validate_json(path.read_text(encoding="utf-8")))

    counts = (
        _write_jsonl(paths.POLICY_CATALOG_CHUNKS, catalog_chunks),
        _write_jsonl(paths.POLICY_CONTENT_CHUNKS, content_chunks),
        _write_jsonl(paths.FAQ_CHUNKS, faq_list),
    )
    print("청크 생성: 정책 탐색 {} · 정책 본문 {} · 1350 FAQ {}".format(*counts))


if __name__ == "__main__":
    main()
