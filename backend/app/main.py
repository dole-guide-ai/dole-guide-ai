from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.routers import health
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.request_id import HEADER as REQUEST_ID_HEADER
from app.core.request_id import RequestIdMiddleware

setup_logging()
settings = get_settings()
settings.warn_missing_keys()


def operation_id(route: APIRoute) -> str:
    # 생성 타입(api.gen.ts)의 operation 이름을 함수명으로 고정합니다.
    return route.name


# Swagger(/docs)·ReDoc·openapi.json은 local에서만 엽니다.
# gen:api는 스크립트로 스키마를 뽑으므로 영향이 없습니다.
is_local = settings.app_env == "local"
app = FastAPI(
    title="Dole Guide API",
    generate_unique_id_function=operation_id,
    docs_url="/docs" if is_local else None,
    redoc_url="/redoc" if is_local else None,
    openapi_url="/openapi.json" if is_local else None,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)
# CORS보다 바깥에 두어 오류·CORS 응답에도 요청 ID가 붙게 합니다.
app.add_middleware(RequestIdMiddleware)
app.include_router(health.router)
