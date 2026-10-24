"""프롬프트 파일을 읽습니다. 프롬프트는 코드 문자열이 아니라 이 폴더의 .md 파일로 둡니다."""

from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent


@cache
def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
