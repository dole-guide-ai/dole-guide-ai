"""수집 데이터 경로. backend/data/knowledge/는 .gitignore 대상입니다."""

from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "knowledge"

RAW = DATA_ROOT / "raw"
PROCESSED = DATA_ROOT / "processed"
VALIDATION = DATA_ROOT / "validation"

WORK24_RAW = RAW / "work24_policies"
WORK24_PROCESSED = PROCESSED / "work24_policies"
FAQ_RAW = RAW / "faq_1350"
FAQ_PROCESSED = PROCESSED / "faq_1350"

MANIFEST = VALIDATION / "crawl_manifest.json"
REPORT = VALIDATION / "validation_report.json"

CHUNKS = DATA_ROOT / "chunks"
POLICY_CATALOG_CHUNKS = CHUNKS / "policy_catalog_chunks.jsonl"
POLICY_CONTENT_CHUNKS = CHUNKS / "policy_content_chunks.jsonl"
FAQ_CHUNKS = CHUNKS / "faq_1350_chunks.jsonl"
