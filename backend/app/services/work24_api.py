"""고용24 OpenAPI 클라이언트 (설계 3.11·데이터 설계 8·9절).

훈련과정 목록(310L01)과 구직자취업역량 강화프로그램(217L01)을 XML로 부릅니다. 호출 하나는
EXTERNAL_API_TIMEOUT_SECONDS(5초)까지 기다리고 실패하면 EXTERNAL_API_RETRIES(1회) 다시 부릅니다.
인증키가 없거나 끝내 실패하면 None을 돌려주고, 서비스가 스냅샷으로 대체합니다.
응답 원본은 저장하지 않고, 인증키가 든 호출 URL은 로그·오류에 남기지 않습니다.
"""

import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import date

import httpx

from app.core.config import get_settings
from app.schemas.trainings import Program, Training

logger = logging.getLogger(__name__)

TRAINING_URL = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
PROGRAM_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo217L01.do"
PAGE_SIZE = 10
TRAINING_SEARCH_DAYS = 60  # 훈련 시작일 검색 구간 (오늘부터)
# 허용값은 API 계약 확인 전이라(데이터 설계 8.8) 공식 예시의 기본값만 씁니다.
_TRAINING_FIXED = {"returnType": "XML", "outType": "1", "sort": "ASC", "sortCol": "2"}


def _get(url: str, params: dict[str, str]) -> ET.Element | None:
    settings = get_settings()
    if not settings.work24_api_key:
        return None
    query = {"authKey": settings.work24_api_key, **params}
    for attempt in range(settings.external_api_retries + 1):
        try:
            res = httpx.get(url, params=query, timeout=settings.external_api_timeout_seconds)
            res.raise_for_status()
            return ET.fromstring(res.content)
        except (httpx.HTTPError, ET.ParseError) as exc:
            # URL에는 인증키가 들어 있어 남기지 않고 오류 종류와 시도 횟수만 남깁니다.
            logger.warning("work24 api failed type=%s attempt=%s", type(exc).__name__, attempt + 1)
    return None


def _text(node: ET.Element, tag: str) -> str | None:
    value = node.findtext(tag)
    return value.strip() if value and value.strip() else None


def _ymd(raw: str | None) -> str | None:
    """20261109 또는 2026-11-09를 2026-11-09로."""
    if not raw:
        return None
    digits = raw.replace("-", "")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}" if len(digits) == 8 else raw


def parse_trainings(root: ET.Element) -> list[Training]:
    """`HRDNet/srchList/scn_list`를 Training으로. 과정 식별은 trprId + trprDegr (8.5)."""
    items = []
    for node in root.iter("scn_list"):
        course_id, degree = _text(node, "trprId"), _text(node, "trprDegr")
        title = _text(node, "title")
        if not course_id or not title:
            continue
        start, end = _ymd(_text(node, "traStartDate")), _ymd(_text(node, "traEndDate"))
        items.append(
            Training(
                id=f"{course_id}:{degree or ''}",
                title=title,
                institution=_text(node, "subTitle") or "",
                period=f"{start or '?'} ~ {end or '?'}",
                region=_text(node, "address"),
                url=_text(node, "titleLink"),
            )
        )
    return items


def parse_programs(root: ET.Element) -> list[Program]:
    """`empPgmSchdInviteList/empPgmSchdInvite`를 Program으로.

    프로그램 API에는 고유 ID·상세 URL이 없어 만들지 않고(9.8), 목록 안 순서로만 구분합니다.
    시작시간은 오전·오후 구분값과 같이 원문 그대로 보여 줍니다(9.5).
    """
    items = []
    for index, node in enumerate(root.iter("empPgmSchdInvite")):
        title = _text(node, "pgmNm")
        if not title:
            continue
        start = _ymd(_text(node, "pgmStdt"))
        end = _ymd(_text(node, "pgmEndt"))
        time_text = " ".join(
            part for part in (_text(node, "openTimeClcd"), _text(node, "openTime")) if part
        )
        period = start if not end or end == start else f"{start} ~ {end}"
        items.append(
            Program(
                id=f"live-{index}",
                title=title,
                type=_text(node, "pgmSubNm") or "",
                schedule=" ".join(part for part in (period, time_text) if part),
                center=_text(node, "orgNm"),
            )
        )
    return items


def fetch_trainings(
    keyword: str | None, today: date, page: int = 1, get: Callable = _get
) -> list[Training] | None:
    start = today.strftime("%Y%m%d")
    end = date.fromordinal(today.toordinal() + TRAINING_SEARCH_DAYS).strftime("%Y%m%d")
    params = {
        **_TRAINING_FIXED,
        "pageNum": str(page),
        "pageSize": str(PAGE_SIZE),
        "srchTraStDt": start,
        "srchTraEndDt": end,
    }
    if keyword:
        params["srchTraProcessNm"] = keyword
    root = get(TRAINING_URL, params)
    return None if root is None else parse_trainings(root)


def fetch_programs(start: date | None, get: Callable = _get) -> list[Program] | None:
    params = {"returnType": "XML", "startPage": "1", "display": str(PAGE_SIZE)}
    if start:
        params["pgmStdt"] = start.strftime("%Y%m%d")
    root = get(PROGRAM_URL, params)
    return None if root is None else parse_programs(root)
