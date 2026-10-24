"""1350 FAQ raw HTML → processed/faq_1350/{faq_catalog.json, details/{id}.json}

uv run python -m scripts.ingest.parse_moel_faq
"""

import re

from scripts.ingest import paths
from scripts.ingest.fetch import save_json
from scripts.ingest.schemas import FaqCatalogItem, FaqDetail
from scripts.ingest.text import soup, strip_noise, text_of

DETAIL_URL = "https://1350.moel.go.kr/home/hp/data/faqView.do?faq_idx={faq_id}"
_FAQ_ID = re.compile(r"faq_idx=(\d+)")


def parse_listing(html: str, page: int) -> list[FaqCatalogItem]:
    items = []
    for position, link in enumerate(soup(html).select('a[data-target*="faq_idx="]'), start=1):
        match = _FAQ_ID.search(link["data-target"])
        if not match:
            continue
        faq_id = match.group(1)
        items.append(
            FaqCatalogItem(
                faq_id=faq_id,
                title=text_of(link.find("p")),
                summary=text_of(link.select_one(".search_value_text_div")),
                list_page=page,
                list_position=position,
                detail_url=DETAIL_URL.format(faq_id=faq_id),
            )
        )
    return items


def reported_total(html: str) -> int | None:
    """검색 결과의 FAQ 탭 건수, 예: FAQ(94)."""
    match = re.search(r"FAQ\((\d+)\)", text_of(soup(html).find("h3", string=re.compile("FAQ"))))
    return int(match.group(1)) if match else None


def parse_detail(html: str, faq_id: str) -> FaqDetail:
    table = strip_noise(soup(html).select_one("table.p-table"))
    fields = {text_of(row.find("th")): row.find("td") for row in table.select("tr.p-td__info")}
    attachments = (
        [text_of(a) for a in fields["첨부파일"].find_all("a")] if "첨부파일" in fields else []
    )
    return FaqDetail(
        faq_id=faq_id,
        title=text_of(table.select_one(".p-table__subject_text")),
        published_at=text_of(table.select_one(".p-author__info time")),
        question=text_of(fields.get("질의")),
        answer=text_of(fields.get("답변")),
        attachments=[name for name in attachments if name],
        source_url=DETAIL_URL.format(faq_id=faq_id),
    )


def main() -> None:
    catalog: list[FaqCatalogItem] = []
    for listing in sorted((paths.FAQ_RAW / "listings").glob("page_*.html")):
        page = int(listing.stem.removeprefix("page_"))
        catalog += parse_listing(listing.read_text(encoding="utf-8"), page)
    save_json(paths.FAQ_PROCESSED / "faq_catalog.json", [item.model_dump() for item in catalog])

    for raw in sorted((paths.FAQ_RAW / "details").glob("*.html")):
        detail = parse_detail(raw.read_text(encoding="utf-8"), raw.stem)
        save_json(paths.FAQ_PROCESSED / "details" / f"{raw.stem}.json", detail.model_dump())
    print(f"목록 {len(catalog)}건 파싱 완료")


if __name__ == "__main__":
    main()
