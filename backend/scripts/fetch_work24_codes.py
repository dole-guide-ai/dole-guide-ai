"""고용24 공통코드 API에서 지역(dtlGb=1)·직종(dtlGb=2)을 받아 data/reference/work24_codes.json을
다시 만듭니다. 서버는 이 스크립트를 쓰지 않고, 고용24 코드가 바뀌었을 때 사람이 돌립니다.

사용: backend/에서 `uv run python scripts/fetch_work24_codes.py`
(backend/.env에 WORK24_API_KEY 필요). 인증키는 출력·저장하지 않습니다.
원본 필드명(regionCd·jobsNm·superCd)은 여기서만 쓰고 JSON은 code·name·parent·depth로 둡니다.
"""

import json
import sys

# 표준 파서는 외부 엔티티를 안 불러오고 expat(2.4+)이 엔티티 폭주를 막습니다. 입력은 고용24 응답뿐.
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.work24_codes import CODES_JSON  # noqa: E402

URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo21L01.do"
LEVELS = ("oneDepth", "twoDepth", "threeDepth")


def fetch(dtl_gb: str, root_tag: str) -> ET.Element:
    key = get_settings().work24_api_key
    if not key:
        sys.exit("backend/.env에 WORK24_API_KEY를 넣어 주세요.")
    params = {"authKey": key, "returnType": "XML", "target": "CMCD", "dtlGb": dtl_gb}
    res = httpx.get(URL, params=params, timeout=30)
    res.raise_for_status()
    root = ET.fromstring(res.content)
    if root.tag != root_tag:  # 인증 실패도 200으로 오므로 루트 태그로 확인
        sys.exit(f"dtlGb={dtl_gb} 응답이 {root_tag}가 아니에요. 인증키·사용 승인을 확인해 주세요.")
    return root


def flatten(root: ET.Element, code_tag: str, name_tag: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str | None, str]] = set()

    def walk(node: ET.Element, parent: str | None, depth: int) -> None:
        code = node.findtext(code_tag)
        if (parent, code) not in seen:  # 같은 상위 아래 같은 코드가 두 번 오면 수집 중복
            seen.add((parent, code))
            rows.append(
                {"code": code, "name": node.findtext(name_tag), "parent": parent, "depth": depth}
            )
        if depth < len(LEVELS):
            for child in node.findall(LEVELS[depth]):
                walk(child, code, depth + 1)

    for top in root.findall(LEVELS[0]):
        walk(top, None, 1)
    return rows


def dump(codes: dict[str, list[dict]]) -> str:
    """리뷰에서 바뀐 코드가 줄 단위로 보이게 한 줄에 코드 하나씩 씁니다."""
    parts = []
    for key, rows in codes.items():
        body = ",\n".join(f"    {json.dumps(r, ensure_ascii=False)}" for r in rows)
        parts.append(f'  "{key}": [\n{body}\n  ]')
    return "{\n" + ",\n".join(parts) + "\n}\n"


if __name__ == "__main__":
    codes = {
        "regions": flatten(fetch("1", "cmcdRegion"), "regionCd", "regionNm"),
        "occupations": flatten(fetch("2", "cmcdJobs"), "jobsCd", "jobsNm"),
    }
    CODES_JSON.parent.mkdir(parents=True, exist_ok=True)
    CODES_JSON.write_text(dump(codes), encoding="utf-8", newline="\n")
    print(f"지역 {len(codes['regions'])}건, 직종 {len(codes['occupations'])}건 → {CODES_JSON.name}")
