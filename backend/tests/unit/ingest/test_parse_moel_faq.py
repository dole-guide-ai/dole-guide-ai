"""1350 FAQ 파서. 실제 페이지 구조를 본뜬 합성 HTML을 씁니다."""

from scripts.ingest.parse_moel_faq import parse_detail, parse_listing, reported_total

LISTING = """
<html><body>
<nav><a href="#">통합검색 홈</a></nav>
<h3><span>FAQ(2)</span></h3>
<a class="menu-link" href="#" data-target="/home/hp/data/faqView.do?faq_idx=9000000001">
  <div><p>합성 질문 하나</p>
  <div class="search_value_text_div">  합성 요약
     하나 </div></div>
</a>
<a class="menu-link" href="#" data-target="/home/hp/data/faqView.do?faq_idx=9000000002">
  <div><p>합성 질문 둘</p><div class="search_value_text_div">합성 요약 둘</div></div>
</a>
<a href="#" data-target="/home/hp/data/notice.do">공지</a>
</body></html>
"""

DETAIL = """
<html><body>
<div>통합검색 홈 서비스 안내 F A Q</div>
<table class="p-table block"><caption>F A Q 상세보기</caption><tbody>
<tr class="p-table__subject"><td colspan="2">
  <span class="p-table__subject_text">합성 질문 하나</span>
  <div class="p-author__info"><span class="p-split"><em class="skip">작성일 :</em>
  <time>2024-01-02</time></span><span class="p-split">조회수 <span>3</span></span></div>
</td></tr>
<tr class="p-td__info"><th class="infol">질의</th><td class="infor">합성 질의 본문</td></tr>
<tr class="p-td__info"><th class="infol">답변</th><td class="infor">
  <div><span>첫째 </span><span>문단</span></div><div><span>둘째 문단</span></div>
  <script>alert(1)</script>
</td></tr>
<tr class="p-td__info"><th class="infol">첨부파일</th><td class="infor">
  <ul class="p-attach"><li><a href="#">합성양식.hwp</a></li></ul>
</td></tr>
</tbody></table>
<footer>Copyright ⓒ</footer>
</body></html>
"""


def test_parse_listing_extracts_ids_titles_and_order():
    items = parse_listing(LISTING, page=3)

    assert [item.faq_id for item in items] == ["9000000001", "9000000002"]
    assert items[0].title == "합성 질문 하나"
    assert items[0].summary == "합성 요약\n하나"
    assert (items[1].list_page, items[1].list_position) == (3, 2)
    assert items[0].detail_url.endswith("faq_idx=9000000001")


def test_parse_listing_returns_empty_for_page_without_results():
    assert parse_listing("<html><body><p>검색 결과 없음</p></body></html>", page=11) == []


def test_reported_total_reads_faq_tab_count():
    assert reported_total(LISTING) == 2


def test_parse_detail_keeps_only_qa_fields_without_noise():
    detail = parse_detail(DETAIL, "9000000001")

    assert detail.title == "합성 질문 하나"
    assert detail.published_at == "2024-01-02"
    assert detail.question == "합성 질의 본문"
    assert detail.answer == "첫째 문단\n둘째 문단"
    assert "alert" not in detail.answer
    assert detail.attachments == ["합성양식.hwp"]
    assert detail.metadata == {"priority": "secondary"}
