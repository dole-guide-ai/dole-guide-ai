"""POST 요청을 한 번만 실행하게 하는 서비스입니다 (Idempotency-Key).

버튼을 두 번 누르거나 네트워크가 끊겨 같은 요청이 다시 오면, 처음 만든 결과를 그대로 돌려줍니다.
같은 키인데 요청 본문이 다르면 409 IDEMPOTENCY_MISMATCH입니다.
키가 없으면 그냥 한 번 실행합니다.

쓰는 법 (서비스 안에서):
    return run_once(db, account.user_id, key, body, ActivityRead, lambda: _create(db, ...))

`create`는 flush까지만 하고 commit하지 않습니다. 결과와 키를 같은 트랜잭션으로 여기서 commit합니다.
"""

import hashlib
import json
import uuid
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.repositories import idempotency as repo
from app.schemas.common import ErrorCode


def request_hash(body: Any) -> str:
    payload = body.model_dump(mode="json") if isinstance(body, BaseModel) else body
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def run_once[T: BaseModel](
    db: Session,
    user_id: uuid.UUID,
    key: str | None,
    body: Any,
    model: type[T],
    create: Callable[[], T],
    status_code: int = 201,
) -> T:
    if key is None:
        result = create()
        db.commit()
        return result

    digest = request_hash(body)
    stored = repo.get(db, user_id, key)
    if stored is not None:
        return _replay(stored, digest, model)

    result = create()
    try:
        repo.add(db, user_id, key, digest, status_code, result.model_dump(mode="json"))
        db.commit()
    except IntegrityError:
        # 같은 키가 거의 동시에 두 번 왔습니다. 먼저 끝난 쪽 결과를 돌려줍니다.
        db.rollback()
        stored = repo.get(db, user_id, key)
        if stored is None:
            raise
        return _replay(stored, digest, model)
    return result


def _replay[T: BaseModel](stored: Any, digest: str, model: type[T]) -> T:
    if stored.request_hash != digest:
        raise ConflictError(code=ErrorCode.IDEMPOTENCY_MISMATCH)
    return model.model_validate(stored.response)
