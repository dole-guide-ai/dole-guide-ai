from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.api.deps import CurrentAccount
from app.api.responses import error_responses
from app.schemas.transcriptions import TranscriptionRead
from app.services import transcriptions as transcription_service

router = APIRouter(prefix="/accounts/{persona_id}", tags=["messages"])


@router.post(
    "/transcriptions",
    summary="말하기 녹음을 글로 바꾸기",
    responses=error_responses(401, 404, 413, 415, 429, 503),
)
def create_transcription(
    _: CurrentAccount, file: Annotated[UploadFile, File()]
) -> TranscriptionRead:
    """녹음(webm·ogg·m4a·mp3·wav, 4MB까지)을 받아 글로 돌려줍니다. 녹음은 저장하지 않습니다.

    대화로 바로 보내지 않습니다. 화면이 글을 입력창에 넣고, 사용자가 확인·수정한 뒤
    `input_kind=voice`로 메시지를 보냅니다.
    형식이 아니면 415 UNSUPPORTED_FILE, 너무 크면 413 FILE_TOO_LARGE,
    음성 인식 모델이 없거나 실패하면 503 LLM_UNAVAILABLE입니다.
    """
    return transcription_service.transcribe(file.file)
