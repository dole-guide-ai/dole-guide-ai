"""고용24 OpenAPI 클라이언트 (설계 3.11·데이터 설계 8·9절).

훈련과정 목록(310L01)과 구직자취업역량 강화프로그램(217L01)을 XML로 부릅니다. 호출 하나는
EXTERNAL_API_TIMEOUT_SECONDS(5초)까지 기다리고 실패하면 EXTERNAL_API_RETRIES(1회) 다시 부릅니다.
API별 인증키가 없거나 끝내 실패하면 None을 돌려주고, 서비스가 스냅샷으로 대체합니다.
응답 원본은 저장하지 않고, 인증키가 든 호출 URL은 로그·오류에 남기지 않습니다.
"""

import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import httpx

from app.core.config import get_settings
from app.schemas.trainings import Program, Training

logger = logging.getLogger(__name__)

TRAINING_URL = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
PROGRAM_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo217L01.do"
PAGE_SIZE = 10
TRAINING_SEARCH_DAYS = 60  # 훈련 시작일 검색 구간 (오늘부터)
# 217L01 openTimeClcd: 1 오전, 2 오후 (9.5)
OPEN_TIME_LABELS = {"1": "오전", "2": "오후"}
# 허용값은 API 계약 확인 전이라(데이터 설계 8.8) 공식 예시의 기본값만 씁니다.
_TRAINING_FIXED = {"returnType": "XML", "outType": "1", "sort": "ASC", "sortCol": "2"}


@dataclass(frozen=True)
class LivePage[T]:
    """실시간 조회 한 페이지와 전체 검색 건수."""

    items: list[T]
    total: int


def _total(root: ET.Element, tag: str, fallback: int) -> int:
    raw = root.findtext(f".//{tag}")
    return int(raw) if raw and raw.strip().isdigit() else fallback


def _api_key(url: str) -> str:
    """고용24 인증키는 API마다 다릅니다."""
    settings = get_settings()
    return {
        TRAINING_URL: settings.work24_training_api_key,
        PROGRAM_URL: settings.work24_program_api_key,
    }[url]


def _get(url: str, params: dict[str, str]) -> ET.Element | None:
    settings = get_settings()
    key = _api_key(url)
    if not key:
        return None
    query = {"authKey": key, **params}
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

    프로그램 API에는 고유 ID·상세 URL이 없어 만들지 않습니다(9.8).
    시작시간은 오전·오후 구분 코드(1·2)를 글로 바꿔 시간 앞에 붙입니다(9.5).
    """
    items = []
    for node in root.iter("empPgmSchdInvite"):
        title = _text(node, "pgmNm")
        if not title:
            continue
        start = _ymd(_text(node, "pgmStdt"))
        end = _ymd(_text(node, "pgmEndt"))
        clcd = _text(node, "openTimeClcd")
        am_pm = OPEN_TIME_LABELS.get(clcd, clcd) if clcd else None
        time_text = " ".join(part for part in (am_pm, _text(node, "openTime")) if part)
        period = start if not end or end == start else f"{start} ~ {end}"
        items.append(
            Program(
                title=title,
                type=_text(node, "pgmSubNm") or "",
                schedule=" ".join(part for part in (period, time_text) if part),
                center=_text(node, "orgNm"),
            )
        )
    return items


def fetch_trainings(
    keyword: str | None, start: date, end: date, page: int = 1, get: Callable = _get
) -> LivePage[Training] | None:
    """훈련 시작일이 start~end인 과정. total은 응답의 전체 검색 건수(scn_cnt)."""
    params = {
        **_TRAINING_FIXED,
        "pageNum": str(page),
        "pageSize": str(PAGE_SIZE),
        "srchTraStDt": start.strftime("%Y%m%d"),
        "srchTraEndDt": end.strftime("%Y%m%d"),
    }
    if keyword:
        params["srchTraProcessNm"] = keyword
    root = get(TRAINING_URL, params)
    if root is None:
        return None
    items = parse_trainings(root)
    return LivePage(items, _total(root, "scn_cnt", len(items)))


def fetch_programs(
    start: date | None, page: int = 1, get: Callable = _get
) -> LivePage[Program] | None:
    """start에 시작하는 프로그램. total은 응답의 전체 건수(total)."""
    params = {"returnType": "XML", "startPage": str(page), "display": str(PAGE_SIZE)}
    if start:
        params["pgmStdt"] = start.strftime("%Y%m%d")
    root = get(PROGRAM_URL, params)
    if root is None:
        return None
    items = parse_programs(root)
    return LivePage(items, _total(root, "total", len(items)))
