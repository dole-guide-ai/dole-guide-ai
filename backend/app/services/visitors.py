"""방문자 토큰을 발급하고 확인하는 서비스입니다.

발급할 때는 무작위 토큰을 만들어 해시만 저장하고 원문은 한 번만 돌려줍니다.
확인할 때는 토큰 해시로 방문자를 찾고, 만료를 마지막 접속 시각부터 다시 7일로 늘립니다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import hash_token, new_visitor_token
from app.repositories import accounts as repo
from app.schemas.accounts import VisitorCreated


@dataclass(frozen=True)
class VisitorContext:
    """라우터가 의존성으로 받는 현재 방문자. DB 모델 대신 필요한 값만 넘깁니다."""

    visitor_id: uuid.UUID


def create_visitor(db: Session, now: datetime) -> VisitorCreated:
    token = new_visitor_token()
    expires_at = now + timedelta(days=get_settings().visitor_ttl_days)
    repo.add_visitor(db, hash_token(token), now, expires_at)
    db.commit()
    return VisitorCreated(visitor_token=token, expires_at=expires_at)


def authenticate(db: Session, token: str | None, now: datetime) -> VisitorContext:
    """토큰으로 방문자를 찾고 만료를 마지막 접속 + TTL로 늘립니다."""
    if not token:
        raise UnauthorizedError()
    visitor = repo.get_visitor_by_token_hash(db, hash_token(token))
    if visitor is None or visitor.expires_at <= now:
        raise UnauthorizedError()
    visitor.last_seen_at = now
    visitor.expires_at = now + timedelta(days=get_settings().visitor_ttl_days)
    db.commit()
    return VisitorContext(visitor.visitor_id)
