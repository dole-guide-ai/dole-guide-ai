"""첨부 읽기(nodes/preprocess.read_attachments): 사진은 받아써 가리고, 등급 0이면 사진째 안 보냄."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.agent.nodes import preprocess
from app.core.config import get_settings


@pytest.fixture
def attach(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """file_id → 합성 파일 경로로 여는 가짜 턴. 받아쓰기는 transcripts[file_id]를 돌려줍니다."""
    files: dict[str, Path] = {}
    transcripts: dict[str, str] = {}
    events: list = []

    def photo(file_id: str, transcript: str) -> None:
        path = tmp_path / f"{file_id}.jpg"
        Image.new("RGB", (20, 20), "white").save(path, "JPEG")
        files[file_id], transcripts[str(path)] = path, transcript

    monkeypatch.setattr(
        preprocess, "tool_context_of", lambda config: SimpleNamespace(db=None, account=None)
    )
    monkeypatch.setattr(preprocess, "turn_of", lambda config: SimpleNamespace(file_ids=list(files)))
    monkeypatch.setattr(
        preprocess.files_service, "open_attachment", lambda db, acc, fid: files.get(fid)
    )
    monkeypatch.setattr(preprocess.images, "transcribe", lambda path: transcripts[path])
    monkeypatch.setattr(preprocess, "emit", events.append)
    monkeypatch.setattr(get_settings(), "image_mode", "vision")
    return SimpleNamespace(photo=photo, events=events)


def test_photo_text_is_masked_and_kept_for_later_turns(attach) -> None:
    attach.photo("p1", "회사명: OO물류\n연락처 010-1234-5678")

    result = preprocess.read_attachments({})

    assert "회사명: OO물류" in result.text
    assert "010-1234-5678" not in result.text and "[전화]" in result.text
    # 등급 1(전화)만 있으면 사진째 보내도 됨
    assert result.vision_files == ["p1"]
    assert [e.status for e in attach.events] == ["started", "finished"]
    assert attach.events[0].name == "parse_file"


def test_photo_with_rrn_is_not_sent_as_image(attach) -> None:
    attach.photo("p1", "성명 홍길동 주민등록번호 900101-1234567")
    attach.photo("p2", "자격증명 지게차운전기능사")

    result = preprocess.read_attachments({})

    assert "900101-1234567" not in result.text and "[주민번호]" in result.text
    assert result.vision_files == ["p2"]


def test_unreadable_photo_asks_retake(attach, monkeypatch: pytest.MonkeyPatch) -> None:
    attach.photo("p1", "")

    def fail(path: str) -> str:
        raise RuntimeError("model down")

    monkeypatch.setattr(preprocess.images, "transcribe", fail)

    result = preprocess.read_attachments({})

    assert result.text == preprocess.UNREADABLE_PHOTO
    assert result.vision_files == []


def test_blank_transcript_asks_retake(attach) -> None:
    attach.photo("p1", "  \n ")

    result = preprocess.read_attachments({})

    assert result.text == preprocess.UNREADABLE_PHOTO
    assert result.vision_files == []


@pytest.mark.parametrize(("mode", "sent"), [("transcribe", []), ("off", [])])
def test_modes(attach, monkeypatch: pytest.MonkeyPatch, mode: str, sent: list) -> None:
    attach.photo("p1", "자격증명 지게차운전기능사")
    monkeypatch.setattr(get_settings(), "image_mode", mode)

    result = preprocess.read_attachments({})

    assert result.vision_files == sent
    assert ("지게차운전기능사" in result.text) is (mode == "transcribe")
