"""서류 GET의 ETag와 PATCH의 If-Match를 맞춰 보는 함수입니다.

이력서·신청서·절차 행에는 고칠 때마다 1씩 오르는 lock_version이 있습니다.
GET 응답에 `ETag: "3"`처럼 내보내고, PATCH는 받은 값을 If-Match로 돌려보냅니다.
그 사이 다른 탭이나 대화가 먼저 고쳤으면 409 VERSION_CONFLICT로 막습니다.

라우터에서 쓰는 법:
    response.headers["ETag"] = etag(row.lock_version)      # GET
    check_if_match(if_match, row.lock_version)             # PATCH (서비스에서)

REST는 If-Match가 필수입니다(`api/deps.require_if_match`, 설계 3.11). 서비스에 None이 오면 확인하지
않는데, 대화 턴의 AI 도구가 헤더 없이 서비스를 바로 부르는 경우입니다.
"""

from app.core.errors import ConflictError
from app.schemas.common import ErrorCode


def etag(lock_version: int) -> str:
    return f'"{lock_version}"'


def check_if_match(if_match: str | None, lock_version: int) -> None:
    if if_match is None:
        return
    sent = if_match.strip().removeprefix("W/")
    if sent != etag(lock_version):
        raise ConflictError(code=ErrorCode.VERSION_CONFLICT)
