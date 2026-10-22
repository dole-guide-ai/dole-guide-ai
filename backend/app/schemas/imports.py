"""고용24 불러오기(모의) 목록의 응답 스키마입니다. 이미 넣은 항목은 is_recorded로 표시합니다."""

from typing import Any

from pydantic import BaseModel


class ImportItem(BaseModel):
    import_id: str
    is_recorded: bool
    values: dict[str, Any]


class ImportList(BaseModel):
    items: list[ImportItem]
    total: int
    source_note: str
