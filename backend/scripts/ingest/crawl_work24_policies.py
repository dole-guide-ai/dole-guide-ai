"""고용24 개인 대상 고용정책: 목록(24개씩)을 빈 쪽이 나올 때까지 받고, 상세를 raw HTML로 저장합니다.

uv run python -m scripts.ingest.crawl_work24_policies
"""

from scripts.ingest import paths
from scripts.ingest.fetch import Fetcher, record, save_text
from scripts.ingest.parse_work24_policies import BASE_URL, parse_listing

LIST_URL = BASE_URL + "/cm/c/f/1100/selecPolicyList.do"
LIST_PARAMS = {
    "polyCnClCd": "",
    "systClId": "",
    "concTrgtSecd": "EBQ04",  # 개인
    "recordCountPerPage": 24,
    "srchKeyWord": "",
}
MAX_PAGES = 20


def crawl(fetcher: Fetcher) -> None:
    policies = {}
    for page in range(1, MAX_PAGES + 1):
        html = fetcher.get(LIST_URL, {**LIST_PARAMS, "currentPageNo": page})
        items = [item for item in parse_listing(html, page) if item.key not in policies]
        if not items:
            break
        save_text(paths.WORK24_RAW / "listings" / f"page_{page:02}.html", html)
        policies |= {item.key: item for item in items}
    print(f"목록 {page - 1}쪽, 정책 {len(policies)}건")

    for key, item in policies.items():
        path = paths.WORK24_RAW / "details" / f"{key}.html"
        if path.exists():
            continue
        try:
            save_text(path, fetcher.get(item.detail_url))
            record("work24_policies", key, item.detail_url, ok=True)
        except RuntimeError as error:
            record("work24_policies", key, item.detail_url, ok=False, error=str(error.__cause__))
            print(f"실패: {key}")


if __name__ == "__main__":
    crawl(Fetcher())
