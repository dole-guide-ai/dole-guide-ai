"""골든셋 실행을 LangSmith 실험으로 남길 때 붙이는 이름과 메타데이터.

실험마다 모델·프롬프트가 무엇이었는지 남겨야 점수 변화의 원인을 찾을 수 있습니다.
프롬프트는 내용 대신 해시만 남깁니다.
"""

import hashlib
import os
from pathlib import Path
from typing import Any

from app.core.config import get_settings

LANGSMITH_SUITE = "dole-guide-ai-golden"
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "app" / "agent" / "prompts"
PROMPT_HASH_LENGTH = 12


def prompts_hash() -> str:
    """prompts/ 아래 .md 전체의 해시. 프롬프트가 하나라도 바뀌면 달라집니다."""
    digest = hashlib.sha256()
    for path in sorted(PROMPTS_DIR.rglob("*.md")):
        digest.update(path.relative_to(PROMPTS_DIR).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:PROMPT_HASH_LENGTH]


def experiment_metadata() -> dict[str, Any]:
    settings = get_settings()
    return {
        "agent": f"{settings.agent_provider}/{settings.agent_model}",
        "extract": f"{settings.extract_provider}/{settings.extract_model}",
        "judge": f"{settings.judge_provider or settings.agent_provider}/"
        f"{settings.judge_model or settings.agent_model}",
        "prompts": prompts_hash(),
        "git": os.environ.get("GITHUB_SHA", "local")[:7],
    }
