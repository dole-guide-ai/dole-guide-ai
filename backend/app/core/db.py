from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


# 제약 이름을 고정해 마이그레이션 diff가 흔들리지 않게 합니다.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]


def create_or_existing[T](
    db: Session, create: Callable[[], T], fetch_existing: Callable[[], T | None]
) -> tuple[T, bool]:
    """만들고 commit합니다. 같은 행이 동시에 먼저 만들어졌으면 되돌리고 그 행을 돌려줍니다.

    버튼 두 번·탭 두 개처럼 같은 요청이 거의 동시에 오면 UNIQUE 제약 때문에 한쪽만 성공합니다.
    두 번째 값은 이번에 새로 만들었는지입니다.
    """
    try:
        created = create()
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = fetch_existing()
        if existing is None:
            raise
        return existing, False
    return created, True
