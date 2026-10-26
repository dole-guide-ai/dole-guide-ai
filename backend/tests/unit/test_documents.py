"""첨부 문서 글자 뽑기(agent/input/documents.py). 파일은 테스트 안에서 만든 합성 값입니다."""

import io
import struct
import zipfile
import zlib

from docx import Document
from PIL import Image

from app.agent.input import documents


def minimal_pdf(text: str) -> bytes:
    """글자 한 줄짜리 최소 PDF(Helvetica). xref 위치를 계산해 넣어야 pypdf가 읽습니다."""
    stream = f"BT /F1 12 Tf 10 50 Td ({text}) Tj ET".encode()
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 100]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj" % number + body + b"endobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def test_pdf_text(tmp_path):
    path = tmp_path / "career.pdf"
    path.write_bytes(minimal_pdf("Hello OO Logistics"))
    assert "Hello OO Logistics" in documents.extract_text(str(path))


def test_docx_paragraphs_and_tables(tmp_path):
    path = tmp_path / "career.docx"
    doc = Document()
    doc.add_paragraph("경력증명서")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "회사명"
    table.cell(0, 1).text = "OO물류"
    doc.save(str(path))

    text = documents.extract_text(str(path))

    assert "경력증명서" in text
    assert "회사명 | OO물류" in text


def test_hwpx_section_text(tmp_path):
    path = tmp_path / "license.hwpx"
    xml = "<hs:sec><hp:p><hp:run><hp:t>자격증명: 지게차운전기능사</hp:t></hp:run></hp:p></hs:sec>"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip")
        archive.writestr("Contents/section0.xml", xml)

    assert documents.extract_text(str(path)) == "자격증명: 지게차운전기능사"


def test_hwpx_entities_are_decoded(tmp_path):
    path = tmp_path / "career.hwpx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Contents/section0.xml", "<hs:sec><hp:t>OO&amp;OO 물류 &lt;본사&gt;</hp:t></hs:sec>"
        )

    assert documents.extract_text(str(path)) == "OO&OO 물류 <본사>"


def test_unknown_or_broken_file_is_empty(tmp_path):
    hwp = tmp_path / "old.hwp"
    hwp.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 16)
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 not really")

    assert documents.extract_text(str(hwp)) == ""
    assert documents.extract_text(str(broken)) == ""


def test_zip_bomb_is_not_read(tmp_path, monkeypatch):
    path = tmp_path / "bomb.hwpx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Contents/section0.xml", "<hp:t>가</hp:t>" + " " * 2048)
    monkeypatch.setattr(documents, "MAX_UNZIPPED_BYTES", 1024)

    assert documents.extract_text(str(path)) == ""


def test_long_text_is_cut(tmp_path):
    path = tmp_path / "long.docx"
    doc = Document()
    doc.add_paragraph("가" * (documents.MAX_DOCUMENT_CHARS + 100))
    doc.save(str(path))

    assert len(documents.extract_text(str(path))) == documents.MAX_DOCUMENT_CHARS


def _record(tag: int, payload: bytes) -> bytes:
    return struct.pack("<I", tag | (len(payload) << 20)) + payload


def _hwp_chars(text: str) -> bytes:
    """한글 형식의 문단 글자. 탭은 실제 파일처럼 8글자 자리 제어 문자로 넣습니다."""
    tab = struct.pack("<8H", 9, 0, 0, 0, 0, 0, 0, 9)
    return tab.join(part.encode("utf-16-le") for part in text.split("\t"))


def _hwp_body(*paragraphs: str) -> bytes:
    # 문단 글자 앞에 표 개체 제어 문자(8글자 자리)를 하나 끼워 건너뛰는지도 봅니다.
    table = struct.pack("<8H", 11, 0, 0, 0, 0, 0, 0, 11)
    records = b"".join(
        _record(documents.HWP_PARA_TEXT, table + _hwp_chars(p) + b"\r\x00") for p in paragraphs
    )
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    return compressor.compress(records) + compressor.flush()


class _FakeOle:
    def __init__(self, properties: int, body: bytes):
        header = b"HWP Document File".ljust(36, b"\0") + struct.pack("<I", properties)
        self.streams = {"FileHeader": header, "BodyText/Section0": body}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listdir(self):
        return [["FileHeader"], ["BodyText", "Section0"]]

    def openstream(self, name):
        key = name if isinstance(name, str) else "/".join(name)
        return io.BytesIO(self.streams[key])


def test_hwp_body_text(tmp_path, monkeypatch):
    path = tmp_path / "career.hwp"
    path.write_bytes(documents.OLE_SIGNATURE + b"\0" * 16)
    body = _hwp_body("경력증명서", "회사명\tOO산업")
    monkeypatch.setattr(documents.olefile, "OleFileIO", lambda p: _FakeOle(1, body))

    assert documents.extract_text(str(path)) == "경력증명서\n회사명\tOO산업"


def test_encrypted_hwp_is_not_read(tmp_path, monkeypatch):
    path = tmp_path / "locked.hwp"
    path.write_bytes(documents.OLE_SIGNATURE + b"\0" * 16)
    monkeypatch.setattr(
        documents.olefile, "OleFileIO", lambda p: _FakeOle(1 | 2, _hwp_body("비밀"))
    )

    assert documents.extract_text(str(path)) == ""


def test_scanned_pdf_has_no_text_but_page_images(tmp_path):
    path = tmp_path / "scan.pdf"
    Image.new("RGB", (200, 100), "white").save(path, "PDF")

    assert documents.extract_text(str(path)) == ""
    pages = documents.pdf_page_images(str(path))
    assert len(pages) == 1 and pages[0].startswith(b"\x89PNG")
