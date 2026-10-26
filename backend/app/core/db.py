from collections.abc import Callable, Iterator
from contextlib import contextmanager
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


@contextmanager
def deferred_commit(db: Session) -> Iterator[None]:
    """안에서 부른 `commit()`을 저장점(savepoint) 확정으로 바꿉니다.

    대화 턴은 계정 잠금을 요청 트랜잭션이 쥐고 있어, 도구가 부른 서비스가 commit하면 턴 도중에
    잠금이 풀립니다. 도구 하나를 저장점 하나로 묶어 실패하면 그 도구 것만 되돌리고, 실제 commit은
    턴이 끝날 때(services/chat.Turn.finish) 한 번 합니다. 서비스 코드는 바꾸지 않습니다.
    """
    savepoint = db.begin_nested()
    original = db.commit
    db.commit = db.flush  # type: ignore[method-assign]
    try:
        yield
    except BaseException:
        if savepoint.is_active:
            savepoint.rollback()
        raise
    else:
        if savepoint.is_active:
            savepoint.commit()
    finally:
        db.commit = original  # type: ignore[method-assign]


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
