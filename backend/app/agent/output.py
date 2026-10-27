"""모델 답을 화면으로 보내기 전에 문장 단위로 거르는 출력 관문.

모델이 드물게 생각 과정이나 다른 언어를 답 끝에 흘립니다(예: "…적어드릴게요. напр? No. Korean.").
글자를 받는 대로 보내면 이미 화면에 나간 뒤라 지울 수 없어서, 문장이 끝날 때마다 검사해서 보냅니다.
우리 서비스 답에 나올 일이 없는 문자(키릴·그리스·아랍·태국·데바나가리·일본 가나)가 든 문장이 나오면
그 문장부터 뒤는 모두 버립니다. 흘린 글은 보통 답 끝에 붙고, 그 뒤 글도 같은 흘림인 경우가 많습니다.
"""

import logging
import re
from collections.abc import Callable

from app.rules.obligations import CENTER_CHECK

logger = logging.getLogger(__name__)

FOREIGN_SCRIPT = re.compile(r"[Ͱ-ϿЀ-ӿ֐-ۿऀ-ॿ฀-๿぀-ヿ]")
# 문장 끝(. ! ? 와 뒤 공백) 또는 줄바꿈까지를 한 덩어리로 봅니다. "1." "3.8"처럼 더 잘게 잘려도
# 이어 붙이면 원문과 같아서 상관없습니다.
_COMPLETE = re.compile(r"[^.!?\n]*(?:[.!?]+[ \t]*|\n)")
# 근거 검사(agent/grounding.py)로 문장을 뺐을 때 답 끝에 붙이는 안내
CHECK_NOTE = CENTER_CHECK


class SentenceStream:
    """글자 조각을 받아 끝난 문장만 돌려줍니다.

    - 다른 언어 문자가 든 문장이 나오면 그 뒤는 모두 버립니다.
    - check가 있으면 문장마다 부르고, 통과하지 못한 문장만 뺍니다(근거 없는 숫자·단정).
      하나라도 빼면 답 끝에 확인 안내(CHECK_NOTE)를 붙입니다.
    """

    def __init__(self, check: Callable[[str], bool] | None = None) -> None:
        self._buffer = ""
        self._kept: list[str] = []
        self._check = check
        self.dropped = False
        self.removed = 0

    def feed(self, chunk: str) -> list[str]:
        self._buffer += chunk
        pieces = []
        end = 0
        for match in _COMPLETE.finditer(self._buffer):
            if match.end() == len(self._buffer) and not match.group().endswith(("\n", " ")):
                break  # "3." 뒤에 숫자가 더 올 수 있어 다음 조각을 기다림
            pieces.append(match.group())
            end = match.end()
        self._buffer = self._buffer[end:]
        return self._pass(pieces)

    def close(self) -> list[str]:
        rest, self._buffer = self._buffer, ""
        out = self._pass([rest] if rest else [])
        if self.removed:
            note = ("" if not self.text or self.text.endswith("\n") else "\n\n") + CHECK_NOTE
            self._kept.append(note)
            out.append(note)
        return out

    @property
    def text(self) -> str:
        """화면에 보낸 글 전체(저장·다음 턴 문맥에 씀)."""
        return "".join(self._kept)

    def _pass(self, pieces: list[str]) -> list[str]:
        out = []
        for piece in pieces:
            if self.dropped:
                break
            if FOREIGN_SCRIPT.search(piece):
                self.dropped = True
                logger.warning("reply_foreign_script_dropped")
                break
            if self._check and piece.strip() and not self._check(piece):
                self.removed += 1
                # 뺀 문장의 줄바꿈은 남겨 목록·문단 모양을 지킵니다.
                if trailing := piece[len(piece.rstrip("\n")) :]:
                    out.append(trailing)
                continue
            out.append(piece)
        self._kept += out
        return out
