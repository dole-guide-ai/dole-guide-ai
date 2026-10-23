"""FastAPI 앱을 조립하는 진입점입니다.

서버가 시작될 때 시연 계정 seed를 personas 테이블에 맞춰 넣고, 하루 한 번 도는 정리 작업을
백그라운드로 띄웁니다.
요청은 바깥부터 요청 ID → BFF 공유 비밀 확인 → CORS 순서로 미들웨어를 지나 라우터에 닿습니다.
라우터는 방문자 발급과 헬스 체크를 빼면 모두 /accounts/{persona_id} 아래 경로를 가집니다.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import (
    accounts,
    activities,
    facts,
    files,
    health,
    imports,
    messages,
    procedure,
    resume,
    rounds,
    trainings,
    visitors,
)
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.request_id import HEADER as REQUEST_ID_HEADER
from app.core.request_id import RequestIdMiddleware
from app.core.security import InternalSecretMiddleware
from app.jobs import cleanup
from app.services.seed import load_personas
from app.services.work24_codes import load_codes_if_empty

setup_logging()
settings = get_settings()
settings.warn_missing_keys()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        with SessionLocal() as db:
            load_personas(db)
            load_codes_if_empty(db)
    except SQLAlchemyError as exc:
        logger.warning("seed load skipped type=%s", type(exc).__name__)
    task = asyncio.create_task(cleanup.run_forever())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def operation_id(route: APIRoute) -> str:
    # 생성 타입(api.gen.ts)의 operation 이름을 함수명으로 고정합니다.
    return route.name


# Swagger(/docs)·ReDoc·openapi.json은 local에서만 엽니다.
is_local = settings.app_env == "local"
app = FastAPI(
    title="Dole Guide API",
    generate_unique_id_function=operation_id,
    docs_url="/docs" if is_local else None,
    redoc_url="/redoc" if is_local else None,
    openapi_url="/openapi.json" if is_local else None,
    lifespan=lifespan,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)
# BFF(Next)에서 온 요청만 받습니다. local에서 값을 비우면 확인하지 않습니다.
app.add_middleware(
    InternalSecretMiddleware, secret=settings.internal_api_secret, allow_docs=is_local
)
# 가장 바깥에 두어 오류·CORS·401 응답에도 요청 ID가 붙게 합니다.
app.add_middleware(RequestIdMiddleware)

app.include_router(health.router)
app.include_router(visitors.router)

for router in (
    accounts.router,
    resume.router,
    procedure.router,
    rounds.router,
    activities.router,
    files.router,
    imports.router,
    facts.router,
    messages.router,
    trainings.router,
):
    app.include_router(router)
