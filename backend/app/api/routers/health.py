from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthRead(BaseModel):
    status: str


@router.get("/health", response_model=HealthRead)
def get_health() -> HealthRead:
    return HealthRead(status="ok")
