"""프롬프트 파일을 읽는 로더입니다 (`.claude/rules/ai.md`: 프롬프트는 코드 문자열이 아니라 파일로).

프롬프트는 이 폴더 아래 `.md` 파일로 둡니다. 영역마다 하위 폴더를 쓰면 됩니다.
`load_prompt("resume/ask")`는 `prompts/resume/ask.md`를 읽습니다. 한 번 읽은 파일은 메모리에 둡니다.
"""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
SUFFIX = ".md"


@lru_cache
def load_prompt(name: str) -> str:
    """`name`(확장자 없이, `/`로 하위 폴더)에 해당하는 프롬프트를 읽습니다.

    폴더 밖을 가리키거나 파일이 없으면 FileNotFoundError를 냅니다.
    """
    path = (PROMPTS_DIR / name).with_suffix(SUFFIX).resolve()
    if not path.is_relative_to(PROMPTS_DIR) or not path.is_file():
        raise FileNotFoundError(f"프롬프트 파일이 없어요: {name}{SUFFIX}")
    return path.read_text(encoding="utf-8").strip()
