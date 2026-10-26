"""문서 첨부(pdf·docx·hwpx)에서 글자를 뽑습니다.

글자가 들어 있는 문서는 OCR 없이 서버 안에서 바로 읽으므로 원본이 외부 모델로 나가지 않습니다.
가리기(pii.mask)는 부르는 쪽이 합니다. hwp(옛 한글 형식)와 스캔한 pdf처럼 글자가 없는 문서는
빈 글을 돌려주고, 대화에서 사진으로 다시 올려 달라고 안내합니다.
"""

import re
import zipfile
from pathlib import Path

from docx import Document
from pypdf import PdfReader

# 한 파일에서 대화로 넘기는 최대 글자 수. 경력증명서·이력서는 보통 1~2쪽이라 넉넉합니다.
MAX_DOCUMENT_CHARS = 4000
# docx·hwpx(zip)를 풀었을 때 크기 상한. 4MB 업로드가 수백 MB로 풀리는 압축 폭탄을 막습니다.
MAX_UNZIPPED_BYTES = 20 * 1024 * 1024
PDF_SIGNATURE = b"%PDF"
ZIP_SIGNATURE = b"PK\x03\x04"
HWPX_SECTION = re.compile(r"Contents/section\d+\.xml")
HWPX_TEXT = re.compile(r"<hp:t(?:\s[^>]*)?>([^<]*)</hp:t>")


def _pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def _docx_text(path: Path) -> str:
    document = Document(str(path))
    lines = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(lines)


def _hwpx_text(archive: zipfile.ZipFile) -> str:
    sections = sorted(n for n in archive.namelist() if HWPX_SECTION.fullmatch(n))
    texts = []
    for name in sections:
        xml = archive.read(name).decode("utf-8", errors="ignore")
        texts.append(" ".join(HWPX_TEXT.findall(xml)))
    return "\n".join(texts)


def _zip_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_UNZIPPED_BYTES:
            return ""
        names = archive.namelist()
        if "word/document.xml" in names:
            return _docx_text(path)
        if any(HWPX_SECTION.fullmatch(n) for n in names):
            return _hwpx_text(archive)
    return ""


def extract_text(path: str) -> str:
    """문서 글자. 형식은 확장자가 아니라 파일 첫 바이트로 정합니다. 못 읽으면 빈 글."""
    file = Path(path)
    head = file.read_bytes()[:4]
    try:
        if head.startswith(PDF_SIGNATURE):
            text = _pdf_text(file)
        elif head.startswith(ZIP_SIGNATURE):
            text = _zip_text(file)
        else:
            return ""
    except Exception:  # 깨진 문서는 대화를 막지 않고 못 읽은 것으로 칩니다.
        return ""
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)[:MAX_DOCUMENT_CHARS]
