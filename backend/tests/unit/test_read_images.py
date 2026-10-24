from pathlib import Path

import pytest

from app.agent.nodes import read_images as node
from app.core.config import get_settings

# 1x1 투명 PNG (합성)
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5f0000000049454e44ae426082"
)


@pytest.fixture
def photo(tmp_path: Path) -> str:
    path = tmp_path / "career.png"
    path.write_bytes(PNG)
    return str(path)


@pytest.fixture
def image_mode(monkeypatch: pytest.MonkeyPatch):
    def _set(mode: str) -> None:
        monkeypatch.setenv("IMAGE_MODE", mode)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


def test_transcribe_masks_numbers_and_appends_text(fake_llm, image_mode, photo) -> None:
    image_mode("transcribe")
    fake_llm(["회사: OO산업\n주민등록번호: 800101-1234567\n재직: 2004.03 ~ 2026.09"])

    out = node.read_images({"message": "경력증명서 사진이에요", "images": [photo]})

    assert node.TRANSCRIPT_HEADER in out["message"]
    assert "OO산업" in out["message"]
    assert "1234567" not in out["message"]
    assert out["images"] == []


def test_vision_keeps_images_for_respond(image_mode, photo) -> None:
    image_mode("vision")

    assert node.read_images({"message": "사진이에요", "images": [photo]}) == {}


def test_off_ignores_images(image_mode, photo) -> None:
    image_mode("off")

    assert node.read_images({"message": "사진이에요", "images": [photo]}) == {"images": []}


def test_non_image_files_are_not_sent(image_mode, tmp_path: Path) -> None:
    image_mode("vision")
    note = tmp_path / "note.png"
    note.write_bytes(b"not an image")

    assert node.read_images({"message": "사진이에요", "images": [str(note)]}) == {"images": []}
