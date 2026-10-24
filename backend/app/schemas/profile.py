"""이력서와 신청서에 보여 줄 기본정보·계좌 표시값 스키마입니다.

계좌는 끝 4자리만 담습니다. 이 값은 화면 응답에만 쓰고 LLM 입력에는 넣지 않습니다.
"""

from pydantic import BaseModel


class ProfileDisplay(BaseModel):
    name: str
    birth_year: int | None = None
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    bank_name: str | None = None
    account_last4: str | None = None
