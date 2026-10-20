"""고용24 정책 파서. 실제 페이지 구조를 본뜬 합성 HTML을 씁니다."""

from scripts.ingest.parse_work24_policies import (
    parse_detail,
    parse_listing,
    reported_total,
    section_type_of,
)

LISTING = """
<html><body>
<p>전체 <span class="txt_total" id="totCnt">2</span>건</p>
<a href="#none" class="box_line" onclick="fn_goPolicyIntro('SC00000001', 'SI00000001')">
  <p><span class="tbl_label b_new">신규</span><span class="tbl_label b_person">개인</span>
  <span class="tbl_label skyblue">고용·창업</span></p>
  <strong class="title">합성 정책 하나</strong><p class="txt_ellipsis">합성 요약 하나</p>
</a>
<a href="#none" class="box_line" onclick="fn_goPolicyIntro('SC00000002', 'SI00000002')">
  <p><span class="tbl_label b_person">개인</span><span class="tbl_label">보육·교육</span></p>
  <strong class="title">합성 정책 둘</strong><p class="txt_ellipsis">합성 요약 둘</p>
</a>
</body></html>
"""

DETAIL = """
<html><body>
<div class="lnb"><h2>고객센터</h2><a href="/menu">메뉴</a></div>
<div class="sub_tl"><h2 class="h2_sb">합성 정책 하나</h2></div>
<div class="list_type right">목차 개요 지원내용</div>
<div class="list_type left">
  <div id="CI00000001"><div class="se-contents"><p><br/></p></div></div>
  <h3 id="CI00000002">신청절차</h3>
  <div class="box_border_type_policy"><div class="se-contents">
    <p><span>가 단계</span><span>→</span><span>나 단계</span><span>→</span><span>다 단계</span></p>
    <p><span>설명 </span><span>문단.</span></p>
    <p>다시 → 나오는 → 화살표</p>
    <table><tr><th>구분</th><th>금액</th></tr>
      <tr><td><p>합성 행</p></td><td>1,000원</td></tr></table>
    <ul><li>항목 하나</li><li>항목 둘</li></ul>
    <script>tracking()</script>
  </div></div>
  <h3 id="CI00000003">자주묻는질문</h3>
  <div class="box_border_type_policy"><div class="se-contents">
    <p><span>◼</span><span>합성 질문?</span></p>
    <p>합성 답변 첫 줄</p>
    <p>합성 답변 둘째 줄</p>
    <p>◼ 두 번째 질문?</p>
    <p>두 번째 답변</p>
  </div></div>
  <h3 id="CI00000004">신청양식</h3>
  <div class="box_border_type_policy"><div class="se-contents">
    <p><a href="/files/form.hwp">합성 신청서</a></p>
  </div></div>
  <h3>유사 제도</h3>
  <div class="box_border_type"><a href="#">합성 유사 정책</a></div>
  <p class="b1_r">최종 수정일: 2026-01-31</p>
</div>
<footer>Copyright</footer>
</body></html>
"""


def test_parse_listing_extracts_ids_labels_and_urls():
    items = parse_listing(LISTING, page=1)

    assert [item.policy_id for item in items] == ["SI00000001", "SI00000002"]
    first = items[0]
    assert (first.syst_cl_id, first.policy_name, first.summary) == (
        "SC00000001",
        "합성 정책 하나",
        "합성 요약 하나",
    )
    assert (first.target_label, first.category_label) == ("개인", "고용·창업")
    assert first.detail_url.endswith("systClId=SC00000001&systId=SI00000001")
    assert reported_total(LISTING) == 2


def test_section_type_of_maps_known_titles():
    assert section_type_of("신청자격") == "eligibility"
    assert section_type_of("신청양식과 이의신청") == "appeals"
    assert section_type_of("알 수 없는 목차") == "other"


def test_parse_detail_builds_sections_without_page_chrome():
    detail = parse_detail(DETAIL, "SI00000001", "https://example.test/detail")

    assert detail.title == "합성 정책 하나"
    assert detail.last_modified == "2026-01-31"
    assert [s.original_title for s in detail.sections] == [
        "개요",
        "신청절차",
        "자주묻는질문",
        "신청양식",
    ]
    assert detail.sections[0].blocks == []
    assert detail.related_policies == ["합성 유사 정책"]
    assert all("메뉴" not in s.text and "Copyright" not in s.text for s in detail.sections)


def test_procedure_keeps_step_order_tables_and_lists():
    procedure = parse_detail(DETAIL, "SI00000001", "u").sections[1]
    blocks = procedure.blocks

    steps = [b for b in blocks if b.type == "step"]
    assert [(b.step_number, b.text) for b in steps] == [
        (1, "가 단계"),
        (2, "나 단계"),
        (3, "다 단계"),
    ]
    assert any(b.type == "paragraph" and b.text == "설명 문단." for b in blocks)
    assert any(b.type == "paragraph" and "화살표" in b.text for b in blocks)
    table = next(b for b in blocks if b.type == "table")
    assert table.rows == [["구분", "금액"], ["합성 행", "1,000원"]]
    assert next(b for b in blocks if b.type == "list").items == ["항목 하나", "항목 둘"]
    assert not any(b.type == "paragraph" and b.text == "합성 행" for b in blocks)
    assert "tracking" not in procedure.text


def test_faq_section_pairs_question_with_following_paragraphs():
    faq = parse_detail(DETAIL, "SI00000001", "u").sections[2]

    assert [(b.question, b.answer) for b in faq.blocks] == [
        ("합성 질문?", "합성 답변 첫 줄\n합성 답변 둘째 줄"),
        ("두 번째 질문?", "두 번째 답변"),
    ]
    assert [b.order for b in faq.blocks] == [1, 2]


def test_related_links_become_absolute_urls():
    detail = parse_detail(DETAIL, "SI00000001", "u")

    assert [(link.name, link.url) for link in detail.related_links] == [
        ("합성 신청서", "https://www.work24.go.kr/files/form.hwp")
    ]


def test_same_policy_id_with_different_class_is_kept_separately():
    html = LISTING.replace("'SC00000002', 'SI00000002'", "'SC00000002', 'SI00000001'")

    keys = [item.key for item in parse_listing(html, page=1)]

    assert keys == ["SI00000001_SC00000001", "SI00000001_SC00000002"]


LOOSE_DETAIL = """
<html><body>
<div class="sub_tl"><h2>합성 정책 셋</h2></div>
<div class="list_type left">
  <h3>지원대상</h3>
  <div class="box_border_type_policy">
    <font size="3">· 첫째 대상</font><div><span><br/></span></div>
    <div><span>· 둘째 </span><span>대상</span></div>
    <span>줄바꿈<br/>으로 나뉜 줄</span>
  </div>
  <h3>자주묻는질문</h3>
  <div class="box_border_type_policy">
    <font><b><u>Q1) 합성 질문?</u></b></font><div><br/></div>
    <div>A) 합성 답변</div><div>- 덧붙임</div>
    <div><b>Q2) 둘째 질문?</b></div><div>A) 둘째 답변</div>
  </div>
</div>
</body></html>
"""


def test_content_without_paragraph_tags_is_not_lost():
    eligibility = parse_detail(LOOSE_DETAIL, "SI00000003", "u").sections[0]

    assert [b.text for b in eligibility.blocks] == [
        "· 첫째 대상",
        "· 둘째 대상",
        "줄바꿈",
        "으로 나뉜 줄",
    ]


def test_faq_supports_q_and_a_prefixes():
    faq = parse_detail(LOOSE_DETAIL, "SI00000003", "u").sections[1]

    assert [(b.question, b.answer) for b in faq.blocks] == [
        ("합성 질문?", "합성 답변\n- 덧붙임"),
        ("둘째 질문?", "둘째 답변"),
    ]


NESTED_DETAIL = """
<html><body>
<div class="sub_tl"><h2>합성 정책 넷</h2></div>
<div class="list_type right"><ul>
  <li><a href="#CI1">지원내용</a></li><li><a href="#CI9">개요</a></li>
</ul></div>
<div class="list_type left">
  <h3 id="CI1">지원내용</h3>
  <div class="box_border_type_policy">
    <table><tr><td>
      <p>틀 안 문단</p>
      <table><tr><th>구분</th><th>금액</th></tr><tr><td>가</td><td>1원</td></tr></table>
    </td></tr></table>
  </div>
  <div id="CI9"><div class="se-contents"><p>중간에 있는 개요</p></div></div>
</div>
</body></html>
"""


def test_wrapper_table_is_unwrapped_and_rows_are_not_duplicated():
    benefits = parse_detail(NESTED_DETAIL, "SI00000004", "u").sections[0]

    assert [b.type for b in benefits.blocks] == ["paragraph", "table"]
    assert benefits.blocks[1].rows == [["구분", "금액"], ["가", "1원"]]


def test_overview_div_is_found_anywhere_and_named_from_toc():
    detail = parse_detail(NESTED_DETAIL, "SI00000004", "u")

    assert detail.toc == ["지원내용", "개요"]
    assert [s.original_title for s in detail.sections] == ["지원내용", "개요"]
    assert detail.sections[1].blocks[0].text == "중간에 있는 개요"
