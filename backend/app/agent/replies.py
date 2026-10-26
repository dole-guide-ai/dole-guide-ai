"""LLM 없이 내보내는 고정 답 (data/templates/replies.json)."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

TEMPLATES = Path(__file__).resolve().parents[2] / "data" / "templates" / "replies.json"

ReplyKey = Literal[
    "greeting",
    "thanks",
    "small_talk",
    "other_stage_edit",
    "stage_not_supported",
    "blocked",
    "pii_masked",
    "not_found",
    "fallback",
    "fallback_sources",
    "doc_failed",
    "recorded_answer",
    "confirmed",
]


@lru_cache(maxsize=1)
def _templates() -> dict[str, str]:
    return json.loads(TEMPLATES.read_text(encoding="utf-8"))


def reply(key: ReplyKey) -> str:
    return _templates()[key]
