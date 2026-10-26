"""올린 서류에서 글을 뽑습니다 (F-09, 노션 「AI 설계」 4절).

원본 이미지·문서는 외부 모델로 보내지 않고 서버에서 먼저 글을 뽑습니다. 뽑은 글은 preprocess가
개인정보를 가린 뒤에만 모델에 넘깁니다. 이력서 서류(resume_doc)는 읽은 뒤 바로 지웁니다.

| 형식 | 읽는 법 |
| --- | --- |
| jpg · png | RapidOCR (로컬 ONNX, CPU) |
| pdf | pypdf 글 레이어 |
| docx | python-docx 문단 · 표 |
| hwpx | zip 안 본문 XML의 글 |
| hwp | OLE의 미리보기 글(PrvText) |
"""

import io
import logging
import re
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from xml.etree import ElementTree

from sqlalchemy.orm import Session

from app.services import files as file_service
from app.services.accounts import AccountContext

logger = logging.getLogger(__name__)

# 이보다 짧게 읽히면 판독 실패로 봅니다(흐린 사진 등).
MIN_TEXT_CHARS = 10
# 모델에 넘기는 서류 글 상한 (한 파일)
MAX_TEXT_CHARS = 6000
HWPX_SECTION = re.compile(r"Contents/section\d+\.xml")
HWP_PREVIEW_STREAM = "PrvText"


@dataclass
class ReadResult:
    texts: list[str] = field(default_factory=list)
    failed: bool = False


def read_files(db: Session, account: AccountContext, file_ids: list[str]) -> ReadResult:
    result = ReadResult()
    for row, path in file_service.files_to_read(db, account, file_ids):
        try:
            text = _extract(row.file_name, path.read_bytes())
        except Exception as exc:  # noqa: BLE001 - 깨진 파일은 판독 실패로 다시 찍기를 묻습니다
            logger.warning("document read failed type=%s", type(exc).__name__)
            text = ""
        finally:
            file_service.discard_after_reading(row, path)
        cleaned = re.sub(r"[ \t]+", " ", text).strip()
        if len(cleaned) < MIN_TEXT_CHARS:
            result.failed = True
            continue
        result.texts.append(cleaned[:MAX_TEXT_CHARS])
    return result


def _extract(file_name: str, content: bytes) -> str:
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    readers = {
        "jpg": _image,
        "jpeg": _image,
        "png": _image,
        "pdf": _pdf,
        "docx": _docx,
        "hwpx": _hwpx,
        "hwp": _hwp,
    }
    reader = readers.get(extension)
    return reader(content) if reader else ""


@lru_cache(maxsize=1)
def _ocr() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _image(content: bytes) -> str:
    result, _ = _ocr()(content)
    return "\n".join(line[1] for line in result or [])


def _pdf(content: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)


def _docx(content: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(content))
    lines = [p.text for p in document.paragraphs]
    for table in document.tables:
        lines += [" | ".join(cell.text for cell in row.cells) for row in table.rows]
    return "\n".join(lines)


def _hwpx(content: bytes) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name in sorted(n for n in archive.namelist() if HWPX_SECTION.fullmatch(n)):
            root = ElementTree.fromstring(archive.read(name))
            lines += [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
    return "\n".join(lines)


def _hwp(content: bytes) -> str:
    import olefile

    with olefile.OleFileIO(io.BytesIO(content)) as ole:
        if not ole.exists(HWP_PREVIEW_STREAM):
            return ""
        return ole.openstream(HWP_PREVIEW_STREAM).read().decode("utf-16-le", errors="ignore")
