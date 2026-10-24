"""파일 업로드의 용도 값과 업로드 결과 응답 스키마입니다."""

from enum import StrEnum

from pydantic import BaseModel


class FilePurpose(StrEnum):
    EVIDENCE = "evidence"
    RESUME_DOC = "resume_doc"


class FileCreated(BaseModel):
    file_id: str
    file_name: str
    mime_type: str
    size: int
