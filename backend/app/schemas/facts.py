"""내 정보 창의 응답 스키마입니다.

사용자가 답한 칸 한 줄과 지울 수 있는지 여부, 그리고 서비스가 저장하지 않는 정보 목록이
들어갑니다.
"""

from datetime import date

from pydantic import BaseModel


class FactRead(BaseModel):
    fact_id: str
    group: str
    label: str
    value: str | None = None
    answered_on: date | None = None
    is_deletable: bool


class FactList(BaseModel):
    items: list[FactRead]
    total: int
    not_stored: list[str]
