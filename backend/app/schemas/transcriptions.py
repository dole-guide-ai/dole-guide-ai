"""말하기(음성 인식) 응답 스키마입니다."""

from pydantic import BaseModel


class TranscriptionRead(BaseModel):
    """녹음을 받아쓴 글. 화면은 이 글을 입력창에 넣고, 사용자가 고친 뒤 보냅니다."""

    text: str
