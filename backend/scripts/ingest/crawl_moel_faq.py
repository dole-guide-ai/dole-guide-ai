"""1350 실업급여 FAQ: 검색 목록을 빈 쪽이 나올 때까지 받고, 상세를 raw HTML로 저장합니다.

uv run python -m scripts.ingest.crawl_moel_faq
"""

from scripts.ingest import paths
from scripts.ingest.fetch import Fetcher, record, save_text
from scripts.ingest.parse_moel_faq import DETAIL_URL, parse_listing

LIST_URL = "https://1350.moel.go.kr/home/hp/data/search.do"
LIST_PARAMS = {
    "menu": "searchMenu",
    "submenu": "search",
    "where": "faq",
    "keyword": "실업급여",
    "sort": "date",
    "sortType": "desc",
}
MAX_PAGES = 50


def crawl(fetcher: Fetcher) -> None:
    faq_ids: list[str] = []
    for page in range(1, MAX_PAGES + 1):
        html = fetcher.get(LIST_URL, {**LIST_PARAMS, "curPage": page})
        new_ids = [item.faq_id for item in parse_listing(html, page) if item.faq_id not in faq_ids]
        if not new_ids:
            break
        save_text(paths.FAQ_RAW / "listings" / f"page_{page:02}.html", html)
        faq_ids += new_ids
    print(f"목록 {page - 1}쪽, FAQ {len(faq_ids)}건")

    for faq_id in faq_ids:
        path = paths.FAQ_RAW / "details" / f"{faq_id}.html"
        url = DETAIL_URL.format(faq_id=faq_id)
        if path.exists():
            continue
        try:
            save_text(path, fetcher.get(url))
            record("faq_1350", faq_id, url, ok=True)
        except RuntimeError as error:
            record("faq_1350", faq_id, url, ok=False, error=str(error.__cause__))
            print(f"실패: {faq_id}")


if __name__ == "__main__":
    crawl(Fetcher())
