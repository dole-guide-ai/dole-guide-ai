"""사진·문서 업로드와 증빙 파일 열기를 맡는 라우터입니다.

이력서 서류는 판독한 뒤 지우고, 구직활동 증빙만 서버에 보관합니다. 파일은 4MB까지이고 자기 계정
파일만 열 수 있습니다.
아직 틀만 있어 501을 돌려줍니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import IdempotencyKey, get_current_account
from app.api.responses import error_responses
from app.core.errors import NotImplementedYetError
from app.schemas.files import FileCreated, FilePurpose

router = APIRouter(
    prefix="/accounts/{persona_id}", tags=["files"], dependencies=[Depends(get_current_account)]
)


@router.post(
    "/files",
    summary="파일 올리기",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404, 413, 415, 501),
)
def upload_file(
    file: Annotated[UploadFile, File()],
    purpose: Annotated[FilePurpose, Form()],
    idempotency_key: IdempotencyKey = None,
) -> FileCreated:
    """사진이나 문서(jpg·png·pdf·hwp·hwpx·docx, 4MB까지)를 올립니다.

    purpose가 resume_doc(이력서 서류)면 판독 뒤 지우고, evidence(구직활동 증빙)면 보관해 활동에
    연결합니다.
    너무 크면 413 FILE_TOO_LARGE, 형식이 안 맞으면 415 UNSUPPORTED_FILE입니다. (아직 구현 전이라
    501)
    """
    raise NotImplementedYetError()


@router.get(
    "/files/{file_id}",
    summary="증빙 파일 열기",
    responses={
        200: {"content": {"application/octet-stream": {}}},
        **error_responses(401, 404, 501),
    },
)
def get_file(file_id: str) -> None:
    """보관한 구직활동 증빙 파일의 본문을 돌려줍니다. 자기 계정 파일만 열 수 있고, 다른 계정
    파일이면 404입니다.
    (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()
