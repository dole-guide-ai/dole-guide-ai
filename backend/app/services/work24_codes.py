"""고용24 공통코드(지역·직종)를 적재하고, 사용자가 말한 직종·지역으로 코드 후보를 찾는 서비스입니다.

원본 XML은 data/reference/work24_codes/에 두고(데이터 설계 4.1), 서버가 시작할 때 테이블이
비어 있으면 적재합니다. 새로 받으려면 scripts/fetch_work24_codes.py를 돌립니다(인증키 필요).
lookup_code는 후보를 최대 3개 돌려주고, 세 번 맞지 않으면 말한 이름만 저장합니다 (상세기획 2-1.4).
"""

# 표준 파서는 외부 엔티티를 안 불러오고 expat(2.4+)이 엔티티 폭주를 막습니다. 입력은 고용24 응답뿐.
import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from app.repositories import work24_codes as repo
from app.repositories.work24_codes import CmcdJobs, CmcdRegion

CODES_DIR = Path(__file__).resolve().parents[2] / "data" / "reference" / "work24_codes"
REGION_XML = CODES_DIR / "region.xml"
JOBS_XML = CODES_DIR / "occupation.xml"
MAX_CANDIDATES = 3
MAX_ATTEMPTS = 3  # 세 번 다시 물어도 안 맞으면 name_only

CodeKind = Literal["occupation", "region"]


@dataclass(frozen=True)
class CodeCandidate:
    code: str
    name: str


def parse_regions(xml: bytes, collected_at: datetime) -> list[CmcdRegion]:
    rows: list[CmcdRegion] = []
    for one in ET.fromstring(xml).iter("oneDepth"):
        rows.append(_region(one, None, 1, collected_at))
        rows += [
            _region(two, one.findtext("regionCd"), 2, collected_at) for two in one.iter("twoDepth")
        ]
    return rows


def _region(node: ET.Element, super_cd: str | None, depth: int, at: datetime) -> CmcdRegion:
    return CmcdRegion(
        regionCd=node.findtext("regionCd"),
        regionNm=node.findtext("regionNm"),
        superCd=super_cd,
        depth=depth,
        collected_at=at,
    )


def parse_jobs(xml: bytes, collected_at: datetime) -> list[CmcdJobs]:
    rows: list[CmcdJobs] = []
    seen: set[tuple[str, ...]] = set()

    def walk(node: ET.Element, path: tuple[str, ...], depth: int) -> None:
        code = node.findtext("jobsCd")
        here = (*path, code)
        if here not in seen:  # 같은 경로가 두 번 오면 수집 중복이라 한 번만 (10.5)
            seen.add(here)
            rows.append(
                CmcdJobs(
                    jobsCd=code,
                    jobsNm=node.findtext("jobsNm"),
                    superCd=node.findtext("superCd"),
                    depth=depth,
                    code_path=list(here),
                    collected_at=collected_at,
                )
            )
        child = {1: "twoDepth", 2: "threeDepth"}.get(depth)
        for sub in node.findall(child) if child else []:
            walk(sub, here, depth + 1)

    for one in ET.fromstring(xml).findall("oneDepth"):
        walk(one, (), 1)
    return rows


def load_codes(db: Session, region_xml: bytes, jobs_xml: bytes) -> tuple[int, int]:
    now = datetime.now(UTC)
    regions, jobs = parse_regions(region_xml, now), parse_jobs(jobs_xml, now)
    repo.replace_all(db, regions, jobs)
    db.commit()
    return len(regions), len(jobs)


def load_codes_if_empty(db: Session) -> int:
    """테이블이 비어 있고 원본 XML이 있으면 적재합니다. 넣은 지역 수(없으면 0)를 돌려줍니다."""
    if repo.count_regions(db) or not (REGION_XML.exists() and JOBS_XML.exists()):
        return 0
    return load_codes(db, REGION_XML.read_bytes(), JOBS_XML.read_bytes())[0]


def lookup_code(db: Session, kind: CodeKind, text: str) -> list[CodeCandidate]:
    """사용자가 말한 직종·지역으로 공통코드 후보를 최대 3개 찾습니다. 없으면 빈 목록."""
    if not text.strip():
        return []
    if kind == "region":
        return [
            CodeCandidate(r.regionCd, r.regionNm)
            for r in repo.search_regions(db, text, MAX_CANDIDATES)
        ]
    return [CodeCandidate(j.jobsCd, j.jobsNm) for j in repo.search_jobs(db, text, MAX_CANDIDATES)]


def name_only(text: str) -> dict[str, str | None]:
    """후보를 세 번 다 아니라고 하면 말한 이름만 저장합니다 (고용24 입력 때 목록에서 고르기)."""
    return {"code": None, "name": text.strip(), "status": "name_only"}
