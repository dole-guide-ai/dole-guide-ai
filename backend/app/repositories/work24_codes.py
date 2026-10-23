"""고용24 공통코드(지역·직종) 테이블 조회·적재."""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.work24_code import CmcdJobs, CmcdRegion


def count_regions(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(CmcdRegion)) or 0


def replace_all(db: Session, regions: list[CmcdRegion], jobs: list[CmcdJobs]) -> None:
    """기존 코드를 지우고 새로 넣습니다. 상위가 먼저 들어가야 FK가 맞습니다."""
    db.execute(delete(CmcdJobs))
    db.execute(delete(CmcdRegion))
    for row in sorted(regions, key=lambda r: r.depth):
        db.add(row)
        db.flush()
    by_path: dict[tuple[str, ...], CmcdJobs] = {}
    for row in sorted(jobs, key=lambda j: j.depth):
        parent = by_path.get(tuple(row.code_path[:-1])) if row.depth > 1 else None
        row.parent_id = parent.id if parent else None
        db.add(row)
        db.flush()
        by_path[tuple(row.code_path)] = row


def search_regions(db: Session, text: str, limit: int) -> list[CmcdRegion]:
    return list(
        db.scalars(
            select(CmcdRegion)
            .where(_nospace(CmcdRegion.regionNm).contains(_strip(text), autoescape=True))
            .order_by(CmcdRegion.depth.desc(), func.length(CmcdRegion.regionNm))
            .limit(limit)
        )
    )


def search_jobs(db: Session, text: str, limit: int) -> list[CmcdJobs]:
    """세부 직종(3단계)에서 이름에 말이 들어간 것을 짧은 이름부터. 띄어쓰기는 무시합니다."""
    return list(
        db.scalars(
            select(CmcdJobs)
            .where(
                CmcdJobs.depth == 3,
                _nospace(CmcdJobs.jobsNm).contains(_strip(text), autoescape=True),
            )
            .order_by(func.length(CmcdJobs.jobsNm), CmcdJobs.jobsCd)
            .limit(limit)
        )
    )


def _strip(text: str) -> str:
    return "".join(text.split())


def _nospace(column):
    return func.replace(column, " ", "")
