"""수집·파싱 결과 검사 → validation/validation_report.json. 오류가 있으면 exit 1.

오류: 건수 불일치, 중복 ID, 수집 실패 기록, raw·JSON 누락, 목록·상세 제목 불일치, 형식 위반,
      화면 목차 누락, 목차 원문과 블록 글자 불일치(100% 일치해야 함), 단계 번호 순서
      청크: 블록·FAQ가 청크에 100% 담김, 최대 토큰, 정책당 탐색 청크 1개, 중복 ID, 참조
경고: 비어 있는 목차(원문이 빈 경우가 있음), 예상 건수와 다름

uv run python -m scripts.ingest.validate
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from scripts.ingest import chunk, parse_moel_faq, parse_work24_policies, paths
from scripts.ingest.fetch import save_json
from scripts.ingest.schemas import (
    Chunk,
    FaqDetail,
    PolicyCatalogItem,
    PolicyDetail,
    PolicySection,
)

# Notion「크롤링 전략」(2026-10-19) 조사 시점 건수. 사이트가 바뀌면 달라질 수 있어 경고로만 봅니다.
EXPECTED = {"faq_1350": 94, "work24_policies": 53}
# 파서가 일부러 떼어 내는 표시: Q/A 표시, 소제목 ◼, 단계 화살표.
# 비교할 때 원문과 블록 양쪽에서 똑같이 뺍니다.
# Q/A 표시는 줄 앞이나, 같은 줄에 이어 쓴 경우 문장 끝(?.) 바로 뒤에 옵니다.
_LINE_MARK = re.compile(r"(?:^|(?<=[?.]))\s*[QA]\s*\d*\s*[).:]", re.MULTILINE)
_MARKS = re.compile(r"\s+|[→◼]")


def _normalize(text: str) -> str:
    return _MARKS.sub("", _LINE_MARK.sub("", text))


def _block_text(section: PolicySection) -> str:
    parts = []
    for b in section.blocks:
        parts += [b.text, b.question, b.answer, *b.items, *("".join(row) for row in b.rows)]
    return "\n".join(part for part in parts if part)


def _text_mismatch(section: PolicySection) -> str | None:
    """목차 원문 글자가 블록에 순서까지 그대로 담겼는지. 다르면 처음 어긋난 곳을 돌려줍니다."""
    source, blocks = _normalize(section.text), _normalize(_block_text(section))
    if source == blocks:
        return None
    at = next(
        (i for i, (a, b) in enumerate(zip(source, blocks, strict=False)) if a != b),
        min(len(source), len(blocks)),
    )
    return (
        f"원문 {len(source)}자·블록 {len(blocks)}자, "
        f"원문 '{source[at : at + 20]}' / 블록 '{blocks[at : at + 20]}'"
    )


def _failed_fetches(source: str) -> list[str]:
    manifest = _read(paths.MANIFEST).get(source, {}) if paths.MANIFEST.exists() else {}
    return sorted(item_id for item_id, entry in manifest.items() if not entry["ok"])


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_ids(ids: list[str], reported: int | None, errors: list[str]) -> None:
    duplicates = sorted(i for i, n in Counter(ids).items() if n > 1)
    if duplicates:
        errors.append(f"중복 ID: {duplicates}")
    if reported is not None and len(set(ids)) != reported:
        errors.append(f"목록 표시 {reported}건 ≠ 수집 {len(set(ids))}건")


def _summary(name: str, ids: list[str], reported: int | None, errors: list, warnings: list) -> dict:
    if name in EXPECTED and len(set(ids)) != EXPECTED[name]:
        warnings.append(f"예상 {EXPECTED[name]}건과 다름: {len(set(ids))}건")
    return {
        "listed": len(ids),
        "unique": len(set(ids)),
        "reported_total": reported,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def check_faq(raw_dir: Path, processed_dir: Path, failed: list[str] | None = None) -> dict:
    errors: list[str] = [f"{i}: 수집 실패 기록" for i in failed or []]
    warnings: list[str] = []
    first = raw_dir / "listings" / "page_01.html"
    reported = (
        parse_moel_faq.reported_total(first.read_text(encoding="utf-8")) if first.exists() else None
    )
    catalog_path = processed_dir / "faq_catalog.json"
    if not catalog_path.exists():
        return _summary("faq_1350", [], reported, ["faq_catalog.json 없음"], warnings)

    catalog = _read(catalog_path)
    ids = [item["faq_id"] for item in catalog]
    _check_ids(ids, reported, errors)
    for item in catalog:
        faq_id = item["faq_id"]
        if not (raw_dir / "details" / f"{faq_id}.html").exists():
            errors.append(f"{faq_id}: raw HTML 없음")
        detail_path = processed_dir / "details" / f"{faq_id}.json"
        if not detail_path.exists():
            errors.append(f"{faq_id}: JSON 없음")
            continue
        try:
            detail = FaqDetail.model_validate(_read(detail_path))
        except ValidationError as error:
            errors.append(f"{faq_id}: 형식 오류 {error.error_count()}개")
            continue
        if detail.title != item["title"]:
            errors.append(f"{faq_id}: 목록·상세 제목 다름")
    return _summary("faq_1350", ids, reported, errors, warnings)


def check_work24(raw_dir: Path, processed_dir: Path, failed: list[str] | None = None) -> dict:
    errors: list[str] = [f"{i}: 수집 실패 기록" for i in failed or []]
    warnings: list[str] = []
    first = raw_dir / "listings" / "page_01.html"
    reported = (
        parse_work24_policies.reported_total(first.read_text(encoding="utf-8"))
        if first.exists()
        else None
    )
    catalog_path = processed_dir / "policy_catalog.json"
    if not catalog_path.exists():
        return _summary("work24_policies", [], reported, ["policy_catalog.json 없음"], warnings)

    catalog = _read(catalog_path)
    ids = [f"{item['policy_id']}_{item['syst_cl_id']}" for item in catalog]
    _check_ids(ids, reported, errors)
    for item in catalog:
        policy_id = f"{item['policy_id']}_{item['syst_cl_id']}"
        if not (raw_dir / "details" / f"{policy_id}.html").exists():
            errors.append(f"{policy_id}: raw HTML 없음")
        detail_path = processed_dir / "policies" / f"{policy_id}.json"
        if not detail_path.exists():
            errors.append(f"{policy_id}: JSON 없음")
            continue
        try:
            detail = PolicyDetail.model_validate(_read(detail_path))
        except ValidationError as error:
            errors.append(f"{policy_id}: 형식 오류 {error.error_count()}개")
            continue
        if detail.title != item["policy_name"]:
            errors.append(f"{policy_id}: 목록·상세 제목 다름")
        if not detail.sections:
            errors.append(f"{policy_id}: 목차 없음")
        titles = {s.original_title for s in detail.sections}
        missing = [title for title in detail.toc if title not in titles]
        if missing:
            errors.append(f"{policy_id}: 화면 목차 누락 {missing}")
        empty = [s.original_title for s in detail.sections if not s.blocks]
        if empty:
            warnings.append(f"{policy_id}: 빈 목차 {empty}")
        for section in detail.sections:
            mismatch = _text_mismatch(section)
            if mismatch:
                errors.append(f"{policy_id}: {section.original_title} 본문 불일치 ({mismatch})")
            steps = [b.step_number for b in section.blocks if b.type == "step"]
            if steps and steps != list(range(1, len(steps) + 1)):
                errors.append(f"{policy_id}: {section.original_title} 단계 번호가 순서대로가 아님")
    return _summary("work24_policies", ids, reported, errors, warnings)


def _squash(text: str) -> str:
    return "".join(text.split())


def _consume(text: str, contents: list[str]) -> str:
    """text가 contents에 순서대로 빠짐없이 담겼는지. 다 담기지 못한 나머지를 돌려줍니다.
    청크마다 앞에서부터 가장 길게 들어 있는 부분을 떼어 냅니다(나뉜 표는 머리행이 반복됨)."""
    remaining = _squash(text)
    for content in map(_squash, contents):
        low, high = 0, len(remaining)
        while low < high:
            mid = (low + high + 1) // 2
            if remaining[:mid] in content:
                low = mid
            else:
                high = mid - 1
        remaining = remaining[low:]
    return remaining


def _load_chunks(path: Path) -> list[Chunk]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Chunk.model_validate_json(line) for line in lines if line.strip()]


def check_chunks(work24_dir: Path, faq_dir: Path, files: dict[str, Path]) -> dict:
    """청크가 processed 블록·FAQ를 100% 담았는지, 크기·ID·참조가 맞는지 확인합니다."""
    errors: list[str] = []
    warnings: list[str] = []
    missing = [str(path.name) for path in files.values() if not path.exists()]
    if missing:
        return {"ok": False, "errors": [f"청크 파일 없음: {missing}"], "warnings": warnings}
    try:
        loaded = {name: _load_chunks(path) for name, path in files.items()}
    except ValidationError as error:
        return {"ok": False, "errors": [f"청크 형식 오류 {error.error_count()}개"], "warnings": []}
    every = [c for chunks in loaded.values() for c in chunks]

    duplicates = sorted(i for i, n in Counter(c.chunk_id for c in every).items() if n > 1)
    if duplicates:
        errors.append(f"중복 청크 ID: {duplicates[:10]}")
    tokens = [chunk.estimate_tokens(c.content) for c in every]
    too_long = [c.chunk_id for c, n in zip(every, tokens, strict=True) if n > chunk.MAX_TOKENS]
    if too_long:
        errors.append(f"최대 {chunk.MAX_TOKENS}토큰 초과: {too_long}")

    catalog = [
        PolicyCatalogItem.model_validate(item) for item in _read(work24_dir / "policy_catalog.json")
    ]
    catalog_ids = Counter(c.policy_id for c in loaded["policy_catalog"])
    for item in catalog:
        if catalog_ids[item.key] != 1:
            errors.append(f"{item.key}: 정책 탐색 청크 {catalog_ids[item.key]}개 (1개여야 함)")

    by_section: dict[str, list[Chunk]] = {}
    for c in loaded["policy_content"]:
        by_section.setdefault(c.section_id or "", []).append(c)
    for item in catalog:
        detail = PolicyDetail.model_validate(_read(work24_dir / "policies" / f"{item.key}.json"))
        for section in detail.sections:
            section_chunks = sorted(
                by_section.pop(section.section_id, []), key=lambda c: c.sequence
            )
            known = {b.block_id for b in section.blocks}
            unknown = {i for c in section_chunks for i in c.block_ids} - known
            if unknown:
                errors.append(f"{section.section_id}: 없는 블록 참조 {sorted(unknown)}")
            for block in section.blocks:
                holders = [c.content for c in section_chunks if block.block_id in c.block_ids]
                if not holders:
                    errors.append(f"{section.section_id}/{block.block_id}: 청크에 없음")
                elif rest := _consume(chunk.render_block(block), holders):
                    where = f"{section.section_id}/{block.block_id}"
                    errors.append(f"{where}: 일부만 담김 (빠진 앞부분 '{rest[:20]}')")
    if by_section:
        errors.append(f"processed에 없는 목차의 청크: {sorted(by_section)[:10]}")

    by_faq: dict[str, list[Chunk]] = {}
    for c in loaded["faq_1350"]:
        by_faq.setdefault(c.faq_id or "", []).append(c)
    for path in sorted((faq_dir / "details").glob("*.json")):
        faq = FaqDetail.model_validate(_read(path))
        faq_chunks = sorted(by_faq.pop(faq.faq_id, []), key=lambda c: c.sequence)
        contents = [c.content for c in faq_chunks]
        if not faq_chunks:
            errors.append(f"{faq.faq_id}: FAQ 청크 없음")
        elif any(_squash(faq.question) not in _squash(text) for text in contents):
            errors.append(f"{faq.faq_id}: 질의가 빠진 청크가 있음")
        elif rest := _consume(faq.answer, contents):
            errors.append(f"{faq.faq_id}: 답변 일부만 담김 (빠진 앞부분 '{rest[:20]}')")
    if by_faq:
        errors.append(f"processed에 없는 FAQ의 청크: {sorted(by_faq)[:10]}")

    short = sum(n < chunk.MIN_TOKENS for n in tokens)
    return {
        "ok": not errors,
        "counts": {name: len(chunks) for name, chunks in loaded.items()},
        "tokens": {
            "max": max(tokens, default=0),
            "mean": round(sum(tokens) / len(tokens)) if tokens else 0,
            f"under_{chunk.MIN_TOKENS}": short,
        },
        "errors": errors,
        "warnings": warnings,
    }


CHUNK_FILES = {
    "policy_catalog": paths.POLICY_CATALOG_CHUNKS,
    "policy_content": paths.POLICY_CONTENT_CHUNKS,
    "faq_1350": paths.FAQ_CHUNKS,
}


def main() -> int:
    report = {
        "faq_1350": check_faq(paths.FAQ_RAW, paths.FAQ_PROCESSED, _failed_fetches("faq_1350")),
        "work24_policies": check_work24(
            paths.WORK24_RAW, paths.WORK24_PROCESSED, _failed_fetches("work24_policies")
        ),
        "chunks": check_chunks(paths.WORK24_PROCESSED, paths.FAQ_PROCESSED, CHUNK_FILES),
    }
    save_json(paths.REPORT, report)
    for name, result in report.items():
        status = "통과" if result["ok"] else "실패"
        size = result.get("unique", result.get("counts"))
        print(
            f"[{status}] {name}: {size}, "
            f"오류 {len(result['errors'])}, 경고 {len(result['warnings'])}"
        )
    return 0 if all(result["ok"] for result in report.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
