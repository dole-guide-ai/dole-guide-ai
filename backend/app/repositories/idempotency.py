"""멱등성 키(idempotency_keys) 조회·저장 레포지토리입니다.

POST 재시도를 막으려고 계정별로 키와 처음 응답을 저장합니다. commit은 서비스가 합니다.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import IdempotencyKey


def get(db: Session, user_id: uuid.UUID, key: str) -> IdempotencyKey | None:
    return db.get(IdempotencyKey, (user_id, key))


def add(
    db: Session,
    user_id: uuid.UUID,
    key: str,
    request_hash: str,
    status_code: int,
    response: dict[str, Any] | None,
) -> None:
    db.add(
        IdempotencyKey(
            user_id=user_id,
            key=key,
            request_hash=request_hash,
            status_code=status_code,
            response=response,
        )
    )
    db.flush()
