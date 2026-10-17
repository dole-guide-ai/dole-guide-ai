"""라우터 `responses=`에 붙이는 공통 오류 응답. Swagger와 api.gen.ts에 오류 형식이 나타납니다.

예: `@router.get("/resumes/{id}", responses=error_responses(404))`
"""

from typing import Any

from app.schemas.common import ErrorResponse


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return {status: {"model": ErrorResponse} for status in (*statuses, 500)}
