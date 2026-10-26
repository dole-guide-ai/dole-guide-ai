"""가드 판정 백엔드.

| 백엔드 | 무엇 | 켜는 법 |
| --- | --- | --- |
| rules | data/guard/patterns.json 정규식 | 늘 켜짐 |
| prompt_guard | Prompt Guard 2 분류기(로컬 CPU) | `prompt_guard` + `uv sync --extra guard` |
| llama_guard | Llama Guard 3(OpenAI 호환 API) 출력 판정 | `llama_guard` + `GUARD_LLM_*` |
| jev | TypeSafe AI Jev 판정 | API 형식 확인 전이라 아직 꺼져 있음 (노션 5-1) |

켜는 이름은 설정 `GUARD_BACKENDS`(쉼표 목록)입니다. 한 백엔드가 실패해도 턴은 막지 않습니다
(다른 층과 도구 검사가 남아 있음). 실패는 종류만 로그로 남깁니다.
"""

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agent import gateway
from app.agent.input import pii
from app.core.config import get_settings

logger = logging.getLogger(__name__)

PATTERNS = Path(__file__).resolve().parents[3] / "data" / "guard" / "patterns.json"
UNTRUSTED_TAG = "untrusted"
# Prompt Guard 2가 공격으로 보는 라벨
PROMPT_GUARD_ATTACK_LABELS = ("MALICIOUS", "LABEL_1", "INJECTION", "JAILBREAK")
LLAMA_GUARD_UNSAFE = "unsafe"


@dataclass(frozen=True)
class Verdict:
    blocked: bool
    # 막은 이유 라벨 (injection · pii_request · assertion · pii · unsafe). 글은 담지 않습니다.
    labels: tuple[str, ...] = ()

    @staticmethod
    def ok() -> Verdict:
        return Verdict(False)


@lru_cache(maxsize=1)
def _patterns() -> dict[str, tuple[re.Pattern[str], ...]]:
    raw = json.loads(PATTERNS.read_text(encoding="utf-8"))
    return {
        key: tuple(re.compile(p, re.IGNORECASE) for p in values)
        for key, values in raw.items()
        if not key.startswith("_")
    }


def _matches(kind: str, text: str) -> bool:
    return any(p.search(text) for p in _patterns()[kind])


def _enabled() -> set[str]:
    raw = get_settings().guard_backends
    return {name.strip() for name in raw.split(",") if name.strip()}


# ── 입력 ─────────────────────────────────────────────


def check_input(text: str) -> Verdict:
    """사용자 글 · 서류 글 · 검색 자료 하나를 판정합니다."""
    labels = [kind for kind in ("injection", "pii_request") if _matches(kind, text)]
    if "prompt_guard" in _enabled() and _prompt_guard_attack(text):
        labels.append("injection")
    return Verdict(bool(labels), tuple(dict.fromkeys(labels)))


@lru_cache(maxsize=1)
def _prompt_guard() -> Any:
    try:
        from transformers import pipeline  # 선택 의존성 (uv sync --extra guard)
    except ImportError:
        logger.warning("guard backend unavailable name=prompt_guard reason=not_installed")
        return None
    return pipeline("text-classification", model=get_settings().prompt_guard_model)


def _prompt_guard_attack(text: str) -> bool:
    classifier = _prompt_guard()
    if classifier is None:
        return False
    try:
        result = classifier(text[:2000])[0]
    except Exception as exc:  # noqa: BLE001 - 분류기 실패는 판정 없음으로
        logger.warning("guard backend failed name=prompt_guard type=%s", type(exc).__name__)
        return False
    return (
        str(result["label"]).upper() in PROMPT_GUARD_ATTACK_LABELS
        and float(result["score"]) >= get_settings().guard_block_threshold
    )


# ── 출력 ─────────────────────────────────────────────


def check_output(text: str) -> Verdict:
    """답 문장을 판정합니다. 막히면 verify가 다시 만들거나 고정 답으로 바꿉니다."""
    labels: list[str] = []
    if _matches("assertion", text):
        labels.append("assertion")
    if pii.detect(text):
        labels.append("pii")
    if "llama_guard" in _enabled() and _llama_guard_unsafe(text):
        labels.append("unsafe")
    return Verdict(bool(labels), tuple(labels))


def _llama_guard_unsafe(text: str) -> bool:
    model = gateway.get_guard_model()
    if model is None:
        return False
    try:
        answer = str(model.invoke([("assistant", text)]).content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("guard backend failed name=llama_guard type=%s", type(exc).__name__)
        return False
    return answer.strip().lower().startswith(LLAMA_GUARD_UNSAFE)


# ── 프롬프트 격리 ─────────────────────────────────────


def untrusted(kind: str, text: str) -> str:
    """외부 글을 데이터로 감쌉니다. 글 안의 태그는 지워 감싼 범위를 벗어나지 못하게 합니다."""
    cleaned = re.sub(rf"</?\s*{UNTRUSTED_TAG}[^>]*>", "", text, flags=re.IGNORECASE)
    return f'<{UNTRUSTED_TAG} kind="{kind}">\n{cleaned}\n</{UNTRUSTED_TAG}>'
