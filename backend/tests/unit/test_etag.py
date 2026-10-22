import pytest

from app.core.errors import ConflictError
from app.core.etag import check_if_match, etag


def test_etag_round_trip() -> None:
    check_if_match(etag(3), 3)
    check_if_match('W/"3"', 3)
    check_if_match(None, 3)  # 헤더 없이 부르는 AI 도구


def test_stale_if_match_is_conflict() -> None:
    with pytest.raises(ConflictError) as exc:
        check_if_match(etag(2), 3)
    assert exc.value.code == "VERSION_CONFLICT"
