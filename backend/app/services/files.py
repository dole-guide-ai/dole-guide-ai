"""사진·문서 업로드와 증빙 파일 열기 서비스입니다 (F-09의 파일 받기 부분).

- 4MB(MAX_UPLOAD_MB)까지, jpg·png·pdf·hwp·hwpx·docx만 받습니다.
  확장자와 파일 첫 바이트(형식 서명)가 둘 다 맞아야 합니다. 이름만 바꾼 파일을 막습니다.
- 실물은 UPLOAD_DIR/{user_id}/{file_id}에 두고, files 행에는 이름·형식·크기·저장 위치만 둡니다.
  계정을 지우거나 7일 정리 때 폴더째 지워집니다(services/accounts.py, maintenance.py).
- 판독(이력서 서류)과 활동 연결(증빙)은 대화 턴·활동 PR에서 합니다.
"""

import hashlib
import uuid
from pathlib import Path, PurePath
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, PayloadTooLargeError, UnsupportedMediaError
from app.models import File
from app.repositories import files as repo
from app.schemas.files import FileCreated, FilePurpose
from app.services.accounts import AccountContext
from app.services.idempotency import run_once

# 확장자 → (MIME, 파일 첫 바이트 후보). hwpx·docx는 zip, hwp는 OLE 복합 문서입니다.
_ZIP = (b"PK\x03\x04",)
FILE_TYPES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "pdf": ("application/pdf", (b"%PDF-",)),
    "hwp": ("application/x-hwp", (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)),
    "hwpx": ("application/hwp+zip", _ZIP),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _ZIP,
    ),
}
FILE_NAME_MAX = 200


def upload(
    db: Session,
    account: AccountContext,
    file_name: str | None,
    stream: BinaryIO,
    purpose: FilePurpose,
    idempotency_key: str | None,
) -> FileCreated:
    content = _read_limited(stream)
    name = _clean_name(file_name)
    mime = _check_type(name, content)
    # 같은 키로 이름이나 내용이 다른 파일을 보내면 다른 요청으로 보고 409입니다.
    body = {
        "purpose": purpose.value,
        "file_name": name,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    written: list[tuple[str, Path]] = []

    def create() -> FileCreated:
        created, path = _store(db, account, name, mime, content, purpose)
        written.append((created.file_id, path))
        return created

    try:
        result = run_once(db, account.user_id, idempotency_key, body, FileCreated, create)
    except Exception:
        # 행 저장·commit이 실패하면 이번 요청이 쓴 실물도 지웁니다.
        _remove_written(written)
        raise
    # 같은 키가 동시에 와서 먼저 끝난 요청의 결과를 돌려받았으면, 이번에 쓴 실물은 쓸모가 없습니다.
    _remove_written([(fid, path) for fid, path in written if fid != result.file_id])
    return result


def open_file(db: Session, account: AccountContext, file_id: str) -> tuple[File, Path]:
    """자기 계정 파일만 엽니다. 남의 파일·없는 파일·지운 파일은 모두 404입니다."""
    try:
        parsed = uuid.UUID(file_id)
    except ValueError:
        raise NotFoundError() from None
    row = repo.get_for_user(db, account.user_id, parsed)
    if row is None:
        raise NotFoundError()
    path = _upload_root() / row.storage_key
    if not path.is_file():
        raise NotFoundError()
    return row, path


def _store(
    db: Session,
    account: AccountContext,
    name: str,
    mime: str,
    content: bytes,
    purpose: FilePurpose,
) -> tuple[FileCreated, Path]:
    """실물을 쓰고 files 행을 flush합니다. commit과 실패 시 정리는 `upload`가 합니다."""
    file_id = uuid.uuid4()
    storage_key = f"{account.user_id}/{file_id}"
    path = _upload_root() / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    row = repo.add(
        db,
        File(
            file_id=file_id,
            user_id=account.user_id,
            purpose=purpose.value,
            file_name=name,
            mime_type=mime,
            size=len(content),
            storage_key=storage_key,
        ),
    )
    created = FileCreated(
        file_id=str(row.file_id), file_name=row.file_name, mime_type=row.mime_type, size=row.size
    )
    return created, path


def _remove_written(written: list[tuple[str, Path]]) -> None:
    for _, path in written:
        path.unlink(missing_ok=True)


def _read_limited(stream: BinaryIO) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    content = stream.read(limit + 1)
    if len(content) > limit:
        raise PayloadTooLargeError()
    if not content:
        raise UnsupportedMediaError()
    return content


def _clean_name(file_name: str | None) -> str:
    # 경로 부분은 버리고 이름만 남깁니다(../ 같은 값 방지). 저장 경로에는 쓰지 않습니다.
    name = PurePath((file_name or "").replace("\\", "/")).name.strip()
    return name[-FILE_NAME_MAX:] or "file"


def _check_type(name: str, content: bytes) -> str:
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in FILE_TYPES:
        raise UnsupportedMediaError()
    mime, signatures = FILE_TYPES[extension]
    if not content.startswith(signatures):
        raise UnsupportedMediaError()
    return mime


def _upload_root() -> Path:
    return Path(get_settings().upload_dir)
