"""방문자·시연 계정·계정 데이터를 조회하고 저장하는 레포지토리입니다.

SQL 조회와 flush까지만 하고, commit과 업무 판단은 서비스가 합니다.
서비스가 계정 행들을 만들 때 쓰도록 필요한 모델 클래스도 함께 내보냅니다.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Persona,
    ProcedureState,
    RecognitionApplication,
    Resume,
    Round,
    User,
    UserProfile,
    Visitor,
)


def add_visitor(db: Session, token_hash: str, now: datetime, expires_at: datetime) -> Visitor:
    visitor = Visitor(token_hash=token_hash, last_seen_at=now, expires_at=expires_at)
    db.add(visitor)
    db.flush()
    return visitor


def get_visitor_by_token_hash(db: Session, token_hash: str) -> Visitor | None:
    return db.scalar(select(Visitor).where(Visitor.token_hash == token_hash))


def upsert_persona(
    db: Session, persona_id: str, display: dict[str, Any], seed: dict[str, Any], sort_order: int
) -> None:
    stmt = insert(Persona).values(
        persona_id=persona_id, display=display, seed=seed, sort_order=sort_order
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Persona.persona_id],
        set_={"display": display, "seed": seed, "sort_order": sort_order},
    )
    db.execute(stmt)


def list_personas(db: Session) -> list[Persona]:
    return list(db.scalars(select(Persona).order_by(Persona.sort_order)))


def get_persona(db: Session, persona_id: str) -> Persona | None:
    return db.get(Persona, persona_id)


def get_user(db: Session, visitor_id: uuid.UUID, persona_id: str) -> User | None:
    return db.scalar(
        select(User).where(User.visitor_id == visitor_id, User.persona_id == persona_id)
    )


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session, visitor_id: uuid.UUID) -> list[User]:
    return list(db.scalars(select(User).where(User.visitor_id == visitor_id)))


def add_all(db: Session, rows: list[object]) -> None:
    db.add_all(rows)
    db.flush()


def delete_user(db: Session, user: User) -> None:
    db.execute(delete(User).where(User.user_id == user.user_id))
    db.flush()


def get_procedure(db: Session, user_id: uuid.UUID) -> ProcedureState | None:
    return db.get(ProcedureState, user_id)


def get_resume(db: Session, user_id: uuid.UUID) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user_id))


def get_profile(db: Session, user_id: uuid.UUID) -> UserProfile | None:
    return db.get(UserProfile, user_id)


def list_rounds(db: Session, user_id: uuid.UUID) -> list[Round]:
    return list(db.scalars(select(Round).where(Round.user_id == user_id).order_by(Round.round_no)))


def get_application(db: Session, round_id: uuid.UUID) -> RecognitionApplication | None:
    return db.scalar(
        select(RecognitionApplication).where(RecognitionApplication.round_id == round_id)
    )


def new_user(visitor_id: uuid.UUID, persona_id: str, anchor_date: object) -> User:
    return User(visitor_id=visitor_id, persona_id=persona_id, anchor_date=anchor_date)


__all__ = [
    "Activity",
    "ProcedureState",
    "RecognitionApplication",
    "Resume",
    "Round",
    "UserProfile",
]
