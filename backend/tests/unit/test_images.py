"""사진 입력 부품 (app/agent/input/images.py)."""

from pathlib import Path

import pytest

from app.agent.input.images import as_image_part, image_parts


def test_image_part_uses_file_content_and_rejects_unknown(tmp_path: Path) -> None:
    """코드래빗 지적: 모르는 형식을 PNG로 꾸며 보내던 문제."""
    jpeg = tmp_path / "photo"  # 확장자 없음
    jpeg.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 10)
    text = tmp_path / "note.png"
    text.write_bytes(b"not an image")

    assert as_image_part(str(jpeg))["image_url"]["url"].startswith("data:image/jpeg;")
    with pytest.raises(ValueError):
        as_image_part(str(text))


def test_image_parts_skips_non_image_files(tmp_path: Path) -> None:
    """사진이 아닌 파일은 어느 사진 모드에서든 모델에 보내지 않습니다."""
    jpeg = tmp_path / "evidence.jpg"
    jpeg.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 10)
    note = tmp_path / "note.png"
    note.write_bytes(b"not an image")

    parts = image_parts([str(note), str(jpeg)])

    assert len(parts) == 1
    assert parts[0]["image_url"]["url"].startswith("data:image/jpeg;")
