"""고용24 공통코드(지역·직종) 조회 응답 스키마입니다."""

from pydantic import BaseModel


class CodeRead(BaseModel):
    code: str
    name: str
    parent: str | None = None  # 상위 코드. 시·도, 직종 대분류는 None
    depth: int  # 지역 1(시·도)·2(시·군·구), 직종 1(대)·2(중)·3(세부)
