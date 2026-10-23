"""고용24 공통코드 API에서 지역(dtlGb=1)·직종(dtlGb=2) XML을 받아 저장하고 DB에 다시 적재합니다.

사용: backend/에서 `uv run python scripts/fetch_work24_codes.py`
(backend/.env에 WORK24_API_KEY 필요)
인증키는 출력·저장하지 않습니다.
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.services.work24_codes import CODES_DIR, JOBS_XML, REGION_XML, load_codes  # noqa: E402

URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo21L01.do"


def fetch(dtl_gb: str, root_tag: str) -> bytes:
    key = get_settings().work24_api_key
    if not key:
        sys.exit("backend/.env에 WORK24_API_KEY를 넣어 주세요.")
    params = {"authKey": key, "returnType": "XML", "target": "CMCD", "dtlGb": dtl_gb}
    res = httpx.get(URL, params=params, timeout=30)
    res.raise_for_status()
    if f"<{root_tag}>" not in res.text:  # 인증 실패도 200으로 오므로 루트 태그로 확인
        sys.exit(f"dtlGb={dtl_gb} 응답에 {root_tag}가 없어요. 인증키·사용 승인을 확인해 주세요.")
    return res.content


if __name__ == "__main__":
    CODES_DIR.mkdir(parents=True, exist_ok=True)
    REGION_XML.write_bytes(fetch("1", "cmcdRegion"))
    JOBS_XML.write_bytes(fetch("2", "cmcdJobs"))
    with SessionLocal() as db:
        regions, jobs = load_codes(db, REGION_XML.read_bytes(), JOBS_XML.read_bytes())
    print(f"지역 {regions}건, 직종 {jobs}건 적재")
