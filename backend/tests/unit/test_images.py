"""사진 입력 부품 (app/agent/input/images.py)."""

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from app.agent.input.images import MAX_SIDE, as_image_part, image_parts


def _photo(path: Path, size: tuple[int, int] = (40, 20), fmt: str = "JPEG") -> Path:
    Image.new("RGB", size, "white").save(path, fmt)
    return path


def _decoded(part: dict) -> Image.Image:
    url = part["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))


def test_image_part_uses_file_content_and_rejects_unknown(tmp_path: Path) -> None:
    """코드래빗 지적: 모르는 형식을 PNG로 꾸며 보내던 문제. 확장자가 아니라 내용으로 봅니다."""
    photo = _photo(tmp_path / "photo")  # 확장자 없음
    text = tmp_path / "note.png"
    text.write_bytes(b"not an image")

    assert _decoded(as_image_part(str(photo))).size == (40, 20)
    with pytest.raises(ValueError):
        as_image_part(str(text))


def test_large_photo_is_shrunk_to_max_side(tmp_path: Path) -> None:
    """휴대폰 사진은 긴 변을 줄여 보냅니다(PNG도 JPEG로)."""
    big = _photo(tmp_path / "big.png", (4000, 3000), "PNG")

    assert _decoded(as_image_part(str(big))).size == (MAX_SIDE, 1200)


def test_broken_photo_is_unreadable_not_crash(tmp_path: Path) -> None:
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 10)

    with pytest.raises(ValueError, match="읽을 수 없는"):
        as_image_part(str(broken))


def test_image_parts_skips_non_image_files(tmp_path: Path) -> None:
    """사진이 아닌 파일은 어느 사진 모드에서든 모델에 보내지 않습니다."""
    photo = _photo(tmp_path / "evidence.jpg")
    note = tmp_path / "note.png"
    note.write_bytes(b"not an image")

    parts = image_parts([str(note), str(photo)])

    assert len(parts) == 1
