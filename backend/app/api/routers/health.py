from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.responses import error_responses
from app.core.db import DbSession

router = APIRouter(tags=["health"])


class HealthRead(BaseModel):
    status: str
    db: str


@router.get("/health", response_model=HealthRead, responses=error_responses())
def get_health(db: DbSession) -> HealthRead:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except SQLAlchemyError:
        db_status = "error"
    return HealthRead(status="ok", db=db_status)
