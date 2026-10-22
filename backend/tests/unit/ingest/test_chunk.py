"""청크 생성: 합성 정책·FAQ로 경계 규칙과 크기 제한을 확인합니다."""

from scripts.ingest import chunk
from scripts.ingest.chunk import (
    MAX_TOKENS,
    employment_type,
    estimate_tokens,
    faq_chunks,
    policy_catalog_chunk,
    policy_content_chunks,
    render_table,
)
from scripts.ingest.schemas import (
    Block,
    FaqDetail,
    PolicyCatalogItem,
    PolicyDetail,
    PolicySection,
)

ITEM = PolicyCatalogItem(
    policy_id="SI00000001",
    syst_cl_id="SC1",
    policy_name="실업급여(상용직)",
    target_label="개인",
    category_label="고용·창업",
    summary="합성 요약",
    list_page=1,
    list_position=1,
    detail_url="https://example.test/p",
)


def _block(order: int, type_: str = "paragraph", **fields) -> Block:
    return Block(block_id=f"b{order:03}", type=type_, order=order, **fields)


def _detail(*sections: PolicySection) -> PolicyDetail:
    return PolicyDetail(
        policy_id="SI00000001",
        syst_cl_id="SC1",
        title="실업급여(상용직)",
        source_url="u",
        sections=list(sections),
    )


def _section(order: int, title: str, type_: str, blocks: list[Block]) -> PolicySection:
    return PolicySection(
        section_id=f"SI00000001_SC1_s{order:02}",
        original_title=title,
        section_type=type_,
        order=order,
        text="",
        blocks=blocks,
    )


def test_render_table_keeps_header_and_pads_ragged_rows():
    assert render_table([["구분", "금액"], ["가"]]) == "| 구분 | 금액 |\n| --- | --- |\n| 가 |  |"


def test_employment_type_only_for_unemployment_benefit():
    assert employment_type("실업급여(일용직)") == "daily"
    assert employment_type("일용직 지원") is None


def test_catalog_chunk_has_one_per_policy_with_listed_fields():
    detail = _detail(_section(1, "개요", "overview", [_block(1, text="본문")]))

    result = policy_catalog_chunk(ITEM, detail)

    assert result.chunk_id == "SI00000001_SC1_catalog"
    assert result.content == (
        "정책: 실업급여(상용직)\n대상: 개인\n분야: 고용·창업\n요약: 합성 요약\n목차: 개요"
    )
    assert result.metadata["employment_type"] == "regular"


def test_small_paragraphs_merge_but_faq_pairs_and_steps_stay_separate():
    detail = _detail(
        _section(1, "지원내용", "benefits", [_block(1, text="가"), _block(2, text="나")]),
        _section(
            2,
            "신청절차",
            "procedure",
            [
                _block(1, "step", step_number=1, text="등록"),
                _block(2, "step", step_number=2, text="신청"),
                _block(3, text="1) 등록"),
                _block(4, text="온라인으로 등록합니다."),
                _block(5, text="2) 신청"),
                _block(6, text="센터에 방문합니다."),
            ],
        ),
        _section(
            3,
            "자주묻는질문",
            "faq",
            [
                _block(1, "faq", question="질문1?", answer="답1"),
                _block(2, "faq", question="질문2?", answer="답2"),
            ],
        ),
        _section(4, "개요", "overview", []),
    )

    chunks = policy_content_chunks(ITEM, detail)

    assert [(c.chunk_type, c.block_ids) for c in chunks] == [
        ("section", ["b001", "b002"]),
        ("step", ["b001", "b002"]),
        ("step", ["b003", "b004"]),
        ("step", ["b005", "b006"]),
        ("faq", ["b001"]),
        ("faq", ["b002"]),
    ]
    assert chunks[1].content == "정책: 실업급여(상용직)\n목차: 신청절차\n1. 등록\n2. 신청"
    assert chunks[4].content.endswith("질문: 질문1?\n답변: 답1")
    assert chunks[0].metadata["original_title"] == "지원내용"


def test_long_table_splits_by_rows_and_repeats_header(monkeypatch):
    monkeypatch.setattr(chunk, "MAX_TOKENS", 120)
    rows = [["구분", "금액"]] + [[f"항목{i:02}", f"{i * 1000}원"] for i in range(30)]
    detail = _detail(_section(1, "지원내용", "benefits", [_block(1, "table", rows=rows)]))

    chunks = policy_content_chunks(ITEM, detail)

    assert len(chunks) > 1
    assert all(estimate_tokens(c.content) <= 120 for c in chunks)
    assert all("| 구분 | 금액 |" in c.content for c in chunks)
    assert all(c.chunk_type == "table" and c.block_ids == ["b001"] for c in chunks)
    joined = "".join(c.content for c in chunks)
    assert all(f"항목{i:02}" in joined for i in range(30))


def test_long_unit_repeats_subtitle_in_later_parts(monkeypatch):
    monkeypatch.setattr(chunk, "MAX_TOKENS", 80)
    body = " ".join(f"문장{i}입니다." for i in range(40))
    detail = _detail(
        _section(
            1, "주의사항", "cautions", [_block(1, "heading", text="부정수급"), _block(2, text=body)]
        )
    )

    chunks = policy_content_chunks(ITEM, detail)

    assert len(chunks) > 1
    assert all("부정수급" in c.content for c in chunks)
    assert all(estimate_tokens(c.content) <= 80 for c in chunks)


def _faq(answer: str) -> FaqDetail:
    return FaqDetail(
        faq_id="9000000001",
        title="합성 제목",
        published_at="2024-01-02",
        question="합성 질의",
        answer=answer,
        source_url="https://example.test/f",
    )


def test_faq_chunk_is_one_pair_with_metadata():
    [only] = faq_chunks(_faq("합성 답변"))

    assert only.chunk_id == "FAQ1350_9000000001_01"
    assert only.content == "제목: 합성 제목\n질의: 합성 질의\n답변: 합성 답변"
    assert only.metadata["priority"] == "secondary"
    assert only.metadata["requires_policy_verification"] is False


def test_long_faq_answer_splits_and_keeps_question():
    answer = "\n".join(f"{i}개월 이내에 신청해야 하는 합성 조건 문장입니다." for i in range(200))

    chunks = faq_chunks(_faq(answer))

    assert len(chunks) > 1
    assert all(c.content.startswith("제목: 합성 제목\n질의: 합성 질의\n답변: ") for c in chunks)
    assert all(estimate_tokens(c.content) <= MAX_TOKENS for c in chunks)
    assert chunks[0].metadata["requires_policy_verification"] is True
