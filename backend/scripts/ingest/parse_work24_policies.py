"""고용24 정책 raw HTML → processed/work24_policies/{policy_catalog.json, {id}.json}

상세 본문은 편집기 HTML이라 문단(p)·표(table)·목록(ul/ol)을 블록으로 나눕니다.
'◼'로 시작하는 문단은 소제목이며,
자주묻는질문 목차에서는 소제목+이어지는 문단을 FAQ 한 쌍으로 묶습니다.

uv run python -m scripts.ingest.parse_work24_policies
"""

import re

from bs4 import Comment, NavigableString, Tag

from scripts.ingest import paths
from scripts.ingest.fetch import save_json
from scripts.ingest.schemas import (
    Block,
    PolicyCatalogItem,
    PolicyDetail,
    PolicySection,
    RelatedLink,
    SectionType,
)
from scripts.ingest.text import BLOCK_TAGS, clean, soup, strip_noise, text_of

BASE_URL = "https://www.work24.go.kr"
DETAIL_URL = BASE_URL + "/cm/c/f/1100/selecSystInfo.do?systClId={syst_cl_id}&systId={policy_id}"
_INTRO = re.compile(r"fn_goPolicyIntro\('(?P<cl>\w+)',\s*'(?P<id>\w+)'\)")
_HEADING_MARK = "◼"
_STEP_ARROW = "→"
# 자주묻는질문의 다른 표기: "Q1) 질문", "A) 답변"
_QUESTION = re.compile(r"^Q\s*\d*\s*[).:]\s*")
_ANSWER = re.compile(r"^A\s*\d*\s*[).:]\s*")

SECTION_TYPES: list[tuple[str, SectionType]] = [
    ("개요", "overview"),
    ("제도소개", "overview"),
    ("지원내용", "benefits"),
    ("서비스 내용", "benefits"),
    ("자격", "eligibility"),
    ("대상", "eligibility"),
    ("절차", "procedure"),
    ("이의신청", "appeals"),
    ("주의", "cautions"),
    ("유의", "cautions"),
    ("서류", "documents"),
    ("양식", "documents"),
    ("자주묻는", "faq"),
    ("유사", "related"),
]


def section_type_of(title: str) -> SectionType:
    for keyword, section_type in SECTION_TYPES:
        if keyword in title:
            return section_type
    return "other"


def parse_listing(html: str, page: int) -> list[PolicyCatalogItem]:
    items = []
    for position, card in enumerate(soup(html).select('a[onclick^="fn_goPolicyIntro"]'), start=1):
        match = _INTRO.search(card["onclick"])
        if not match:
            continue
        labels = [text_of(label) for label in card.select(".tbl_label:not(.b_new)")]
        items.append(
            PolicyCatalogItem(
                policy_id=match["id"],
                syst_cl_id=match["cl"],
                policy_name=text_of(card.select_one("strong.title")),
                target_label=labels[0] if labels else "",
                category_label=labels[-1] if len(labels) > 1 else "",
                summary=text_of(card.select_one("p.txt_ellipsis")),
                list_page=page,
                list_position=position,
                detail_url=DETAIL_URL.format(syst_cl_id=match["cl"], policy_id=match["id"]),
            )
        )
    return items


def reported_total(html: str) -> int | None:
    total = soup(html).select_one("#totCnt")
    return int(text_of(total)) if total and text_of(total).isdigit() else None


def _rows(table: Tag) -> list[Tag]:
    """이 표에 직접 속한 행만. 칸 안에 든 다른 표의 행은 세지 않습니다."""
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def _cells(row: Tag) -> list[Tag]:
    return row.find_all(["th", "td"], recursive=False)


def _wrapper_cell(table: Tag) -> Tag | None:
    rows = _rows(table)
    if len(rows) == 1 and len(cells := _cells(rows[0])) == 1:
        return cells[0]
    return None


def _segments(root: Tag) -> list[tuple[str, str | Tag]]:
    """본문을 문서 순서대로 ("text", 한 줄) 또는 ("table"|"ul"|"ol", 태그)로 나눕니다.

    정책마다 p·div·font 등 쓰는 태그가 달라서, 특정 태그를 찾지 않고
    블록 태그와 br을 줄 경계로 삼아 모든 글자를 빠짐없이 담습니다.
    """
    segments: list[tuple[str, str | Tag]] = []
    buffer: list[str] = []

    def flush() -> None:
        for line in clean("".join(buffer)).split("\n"):
            if line.strip():
                segments.append(("text", line.strip()))
        buffer.clear()

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                buffer.append(str(child).replace("\n", " "))
            elif child.name == "br":
                buffer.append("\n")
            elif child.name == "table" and (cell := _wrapper_cell(child)) is not None:
                # 칸 하나짜리 틀 표는 벗기고 안쪽 내용을 읽습니다.
                buffer.append("\n")
                walk(cell)
                buffer.append("\n")
            elif child.name in ("table", "ul", "ol"):
                flush()
                segments.append((child.name, child))
            elif child.name in BLOCK_TAGS:
                buffer.append("\n")
                walk(child)
                buffer.append("\n")
            else:
                walk(child)

    walk(root)
    flush()
    return segments


def _blocks(container: Tag, section_type: SectionType) -> list[Block]:
    blocks: list[Block] = []

    def add(type_: str, **fields) -> None:
        order = len(blocks) + 1
        blocks.append(Block(block_id=f"b{order:03}", type=type_, order=order, **fields))

    for kind, node in _segments(container):
        if kind == "table":
            rows = [[text_of(cell) for cell in _cells(tr)] for tr in _rows(node)]
            add("table", rows=[row for row in rows if any(row)])
        elif kind in ("ul", "ol"):
            items = [text_of(li) for li in node.find_all("li", recursive=False)]
            add("list", items=[item for item in items if item])
        else:
            text = node
            if text.startswith(_HEADING_MARK):
                add("heading", text=clean(text.removeprefix(_HEADING_MARK)))
            elif section_type == "faq" and _QUESTION.match(text):
                add("heading", text=clean(_QUESTION.sub("", text, count=1)))
            elif (
                section_type == "procedure"
                and text.count(_STEP_ARROW) >= 2
                and not any(b.type == "step" for b in blocks)
            ):
                # 절차 요약 줄(가 → 나 → 다) 하나만 단계로 나눕니다.
                for number, step in enumerate(text.split(_STEP_ARROW), start=1):
                    add("step", step_number=number, text=clean(step))
            else:
                add("paragraph", text=text)
    return _pair_faq(blocks) if section_type == "faq" else blocks


def _pair_faq(blocks: list[Block]) -> list[Block]:
    """소제목(질문) 다음 문단들(답변)을 FAQ 블록 하나로 묶습니다."""
    paired: list[Block] = []
    for block in blocks:
        if block.type == "heading":
            paired.append(Block(block_id="", type="faq", order=0, question=block.text))
        elif paired and paired[-1].type == "faq":
            answer = (
                block.text or "\n".join(block.items) or "\n".join(" | ".join(r) for r in block.rows)
            )
            answer = _ANSWER.sub("", answer, count=1)
            paired[-1].answer = clean(f"{paired[-1].answer}\n{answer}")
        else:
            paired.append(block)
    for order, block in enumerate(paired, start=1):
        block.block_id, block.order = f"b{order:03}", order
    return paired


def _links(container: Tag) -> list[RelatedLink]:
    links = []
    for a in container.find_all("a", href=True):
        href, name = a["href"], text_of(a)
        if not name or href.startswith(("#", "javascript")):
            continue
        links.append(
            RelatedLink(name=name, url=href if href.startswith("http") else BASE_URL + href)
        )
    return links


def parse_detail(html: str, policy_id: str, source_url: str, syst_cl_id: str = "") -> PolicyDetail:
    page = soup(html)
    body = strip_noise(page.select_one("div.list_type.left"))
    title = text_of(page.select_one("div.sub_tl h2"))
    toc = [text_of(a) for a in page.select("div.list_type.right ul a")]

    # (목차명, 본문 컨테이너) 목록을 문서 순서대로 만듭니다.
    # 보통은 h3 + 다음 div지만, 개요는 h3 없이 id 달린 div 하나로 들어 있고
    # 위치도 정책마다 다릅니다.
    # 이름은 화면 목차의 링크(#id)에서 찾습니다.
    toc_by_id = {
        a["href"].removeprefix("#"): text_of(a)
        for a in page.select("div.list_type.right ul a[href^='#']")
    }
    parts: list[tuple[str, Tag]] = []
    for element in body.find_all(recursive=False):
        if element.name == "h3":
            content = element.find_next_sibling()
            if content is not None and content.name == "div":
                parts.append((text_of(element), content))
        elif element.name == "div" and element.get("id"):
            parts.append((toc_by_id.get(element["id"], "개요"), element))

    sections, related_links, related_policies = [], [], []
    for order, (original_title, content) in enumerate(parts, start=1):
        section_type = section_type_of(original_title)
        if section_type == "related":
            related_policies = [text_of(a) for a in content.find_all("a") if text_of(a)]
            continue
        # text_of는 트리에 줄바꿈을 끼워 넣으므로 블록을 먼저 만듭니다.
        blocks = _blocks(content, section_type)
        related_links += _links(content)
        sections.append(
            PolicySection(
                section_id=f"{policy_id}_{syst_cl_id}_s{order:02}"
                if syst_cl_id
                else f"{policy_id}_s{order:02}",
                original_title=original_title,
                section_type=section_type,
                order=order,
                text=text_of(content),
                blocks=blocks,
            )
        )

    modified = re.search(r"최종 수정일\s*:\s*(\d{4}-\d{2}-\d{2})", body.get_text(" "))
    return PolicyDetail(
        policy_id=policy_id,
        syst_cl_id=syst_cl_id,
        title=title,
        source_url=source_url,
        toc=toc,
        last_modified=modified.group(1) if modified else None,
        sections=sections,
        related_links=related_links,
        related_policies=related_policies,
    )


def main() -> None:
    catalog: list[PolicyCatalogItem] = []
    for listing in sorted((paths.WORK24_RAW / "listings").glob("page_*.html")):
        page = int(listing.stem.removeprefix("page_"))
        catalog += parse_listing(listing.read_text(encoding="utf-8"), page)
    save_json(
        paths.WORK24_PROCESSED / "policy_catalog.json", [item.model_dump() for item in catalog]
    )

    for item in catalog:
        raw = paths.WORK24_RAW / "details" / f"{item.key}.html"
        if not raw.exists():
            continue
        detail = parse_detail(
            raw.read_text(encoding="utf-8"), item.policy_id, item.detail_url, item.syst_cl_id
        )
        save_json(paths.WORK24_PROCESSED / "policies" / f"{item.key}.json", detail.model_dump())
    print(f"목록 {len(catalog)}건 파싱 완료")


if __name__ == "__main__":
    main()
