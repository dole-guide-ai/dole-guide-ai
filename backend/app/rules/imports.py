"""고용24 불러오기 항목을 이미 넣었는지 판단하는 순수 함수입니다. DB와 HTTP를 모릅니다."""

from typing import Any


def is_recorded(raw: dict[str, Any], recorded: set[str] | None, name: str | None = None) -> bool:
    """recorded가 None이면 seed 표시를, 아니면 이름이 recorded에 있는지 봅니다."""
    if recorded is None:
        return bool(raw.get("is_recorded", False))
    return (name or raw["title"]) in recorded
