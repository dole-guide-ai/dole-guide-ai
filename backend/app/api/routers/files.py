from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentAccount, IdempotencyKey
from app.api.responses import error_responses
from app.core.db import DbSession
from app.schemas.files import FileCreated, FilePurpose
from app.services import files as file_service

router = APIRouter(prefix="/accounts/{persona_id}", tags=["files"])


@router.post(
    "/files",
    summary="파일 올리기",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404, 409, 413, 415),
)
def upload_file(
    db: DbSession,
    account: CurrentAccount,
    file: Annotated[UploadFile, File()],
    purpose: Annotated[FilePurpose, Form()],
    idempotency_key: IdempotencyKey = None,
) -> FileCreated:
    """사진이나 문서(jpg·png·pdf·hwp·hwpx·docx, 4MB까지)를 올립니다.

    purpose가 resume_doc(이력서 서류)면 판독 뒤 지우고, evidence(구직활동 증빙)면 보관해 활동에
    연결합니다.
    너무 크면 413 FILE_TOO_LARGE, 확장자나 파일 내용 형식이 안 맞으면 415 UNSUPPORTED_FILE.
    같은 Idempotency-Key로 다시 보내면 처음 결과를 돌려주고, 내용이 다르면 409.
    """
    return file_service.upload(db, account, file.filename, file.file, purpose, idempotency_key)


@router.get(
    "/files/{file_id}",
    summary="증빙 파일 열기",
    responses={
        200: {"content": {"application/octet-stream": {}}},
        **error_responses(401, 404),
    },
    response_class=FileResponse,
)
def get_file(db: DbSession, account: CurrentAccount, file_id: str) -> FileResponse:
    """보관한 구직활동 증빙 파일의 본문을 돌려줍니다. 자기 계정 파일만 열 수 있고, 다른 계정
    파일이면 404입니다.
    """
    row, path = file_service.open_file(db, account, file_id)
    return FileResponse(
        path,
        media_type=row.mime_type,
        filename=row.file_name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )
