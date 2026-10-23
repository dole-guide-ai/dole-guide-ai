"""검증 스크립트: 임시 폴더에 합성 결과를 만들어 오류·경고를 확인합니다."""

import json
from pathlib import Path

from scripts.ingest.validate import check_chunks, check_faq, check_work24


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")


def _faq(faq_id: str, title: str = "합성 질문") -> dict:
    return {
        "faq_id": faq_id,
        "title": title,
        "published_at": "2024-01-02",
        "question": "합성 질의",
        "answer": "합성 답변",
        "source_url": "https://example.test",
    }


def _faq_fixture(tmp_path: Path, ids: list[str], detail_ids: list[str]) -> tuple[Path, Path]:
    raw, processed = tmp_path / "raw", tmp_path / "processed"
    _write(raw / "listings" / "page_01.html", f"<h3><span>FAQ({len(set(ids))})</span></h3>")
    catalog = [{"faq_id": i, "title": "합성 질문"} for i in ids]
    _write(processed / "faq_catalog.json", catalog)
    for faq_id in detail_ids:
        _write(raw / "details" / f"{faq_id}.html", "<html></html>")
        _write(processed / "details" / f"{faq_id}.json", _faq(faq_id))
    return raw, processed


def test_check_faq_passes_for_complete_data(tmp_path):
    result = check_faq(*_faq_fixture(tmp_path, ["1", "2"], ["1", "2"]))

    assert result["ok"] is True
    assert (result["unique"], result["reported_total"]) == (2, 2)
    assert any("예상" in w for w in result["warnings"])


def test_check_faq_reports_duplicates_and_missing_files(tmp_path):
    result = check_faq(*_faq_fixture(tmp_path, ["1", "1", "2"], ["1"]))

    assert result["ok"] is False
    assert any("중복 ID" in e for e in result["errors"])
    assert "2: raw HTML 없음" in result["errors"]
    assert "2: JSON 없음" in result["errors"]


def test_check_faq_reports_title_mismatch_and_empty_answer(tmp_path):
    raw, processed = _faq_fixture(tmp_path, ["1", "2"], ["1", "2"])
    _write(processed / "details" / "1.json", _faq("1", title="다른 제목"))
    _write(processed / "details" / "2.json", {**_faq("2"), "answer": ""})

    errors = check_faq(raw, processed)["errors"]

    assert "1: 목록·상세 제목 다름" in errors
    assert any(e.startswith("2: 형식 오류") for e in errors)


def test_check_work24_warns_empty_section_and_errors_on_step_gap(tmp_path):
    raw, processed = tmp_path / "raw", tmp_path / "processed"
    _write(raw / "listings" / "page_01.html", '<span id="totCnt">1</span>')
    _write(raw / "details" / "SI00000001_SC1.html", "<html></html>")
    _write(
        processed / "policy_catalog.json",
        [{"policy_id": "SI00000001", "syst_cl_id": "SC1", "policy_name": "합성 정책"}],
    )
    step = {"block_id": "b001", "type": "step", "order": 1}
    _write(
        processed / "policies" / "SI00000001_SC1.json",
        {
            "policy_id": "SI00000001",
            "title": "합성 정책",
            "source_url": "u",
            "sections": [
                {
                    "section_id": "s1",
                    "original_title": "개요",
                    "section_type": "overview",
                    "order": 1,
                    "text": "",
                    "blocks": [],
                },
                {
                    "section_id": "s2",
                    "original_title": "신청절차",
                    "section_type": "procedure",
                    "order": 2,
                    "text": "t",
                    "blocks": [{**step, "step_number": 1}, {**step, "step_number": 3}],
                },
            ],
        },
    )

    result = check_work24(raw, processed)

    assert "SI00000001_SC1: 신청절차 단계 번호가 순서대로가 아님" in result["errors"]
    assert "SI00000001_SC1: 빈 목차 ['개요']" in result["warnings"]


def test_check_reports_missing_catalog(tmp_path):
    assert check_work24(tmp_path, tmp_path)["errors"] == ["policy_catalog.json 없음"]


def test_check_work24_errors_when_blocks_miss_section_text(tmp_path):
    raw, processed = tmp_path / "raw", tmp_path / "processed"
    _write(raw / "details" / "SI00000001_SC1.html", "<html></html>")
    _write(
        processed / "policy_catalog.json",
        [{"policy_id": "SI00000001", "syst_cl_id": "SC1", "policy_name": "합성 정책"}],
    )
    paragraph = {"block_id": "b001", "type": "paragraph", "order": 1, "text": "앞부분"}
    section = {
        "section_id": "s1",
        "original_title": "지원대상",
        "section_type": "eligibility",
        "order": 1,
        "text": "앞부분 그리고 놓친 아주 긴 뒷부분",
        "blocks": [paragraph],
    }
    detail = {"policy_id": "SI00000001", "title": "합성 정책", "source_url": "u"}
    _write(processed / "policies" / "SI00000001_SC1.json", {**detail, "sections": [section]})

    errors = check_work24(raw, processed)["errors"]

    assert any(e.startswith("SI00000001_SC1: 지원대상 본문 불일치") for e in errors)


def test_check_work24_errors_on_missing_toc_entry_and_failed_fetch(tmp_path):
    raw, processed = tmp_path / "raw", tmp_path / "processed"
    _write(raw / "details" / "SI00000001_SC1.html", "<html></html>")
    _write(
        processed / "policy_catalog.json",
        [{"policy_id": "SI00000001", "syst_cl_id": "SC1", "policy_name": "합성 정책"}],
    )
    question = {"block_id": "b001", "type": "faq", "order": 1, "question": "질문?", "answer": "답"}
    section = {
        "section_id": "s1",
        "original_title": "자주묻는질문",
        "section_type": "faq",
        "order": 1,
        "text": "Q1) 질문?A) 답",
        "blocks": [question],
    }
    detail = {"policy_id": "SI00000001", "title": "합성 정책", "source_url": "u"}
    _write(
        processed / "policies" / "SI00000001_SC1.json",
        {**detail, "toc": ["개요", "자주묻는질문"], "sections": [section]},
    )

    errors = check_work24(raw, processed, failed=["SI00000002_SC2"])["errors"]

    assert errors == [
        "SI00000002_SC2: 수집 실패 기록",
        "SI00000001_SC1: 화면 목차 누락 ['개요']",
    ]


def _chunk_fixture(tmp_path: Path, policy_chunk_text: str, faq_chunk_text: str) -> dict:
    work24, faq = tmp_path / "work24", tmp_path / "faq"
    _write(
        work24 / "policy_catalog.json",
        [
            {
                "policy_id": "SI00000001",
                "syst_cl_id": "SC1",
                "policy_name": "합성 정책",
                "target_label": "개인",
                "category_label": "",
                "summary": "",
                "list_page": 1,
                "list_position": 1,
                "detail_url": "u",
            }
        ],
    )
    block = {"block_id": "b001", "type": "paragraph", "order": 1, "text": "합성 본문 전체"}
    section = {
        "section_id": "SI00000001_SC1_s01",
        "original_title": "개요",
        "section_type": "overview",
        "order": 1,
        "text": "합성 본문 전체",
        "blocks": [block],
    }
    detail = {"policy_id": "SI00000001", "title": "합성 정책", "source_url": "u"}
    _write(work24 / "policies" / "SI00000001_SC1.json", {**detail, "sections": [section]})
    _write(faq / "details" / "1.json", _faq("1"))

    def line(**fields) -> str:
        return json.dumps({"sequence": 1, **fields}, ensure_ascii=False)

    files = {
        "policy_catalog": tmp_path / "c.jsonl",
        "policy_content": tmp_path / "p.jsonl",
        "faq_1350": tmp_path / "f.jsonl",
    }
    common = {"policy_id": "SI00000001_SC1"}
    _write(
        files["policy_catalog"],
        line(chunk_id="a", chunk_scope="catalog", chunk_type="catalog", content="정책", **common),
    )
    _write(
        files["policy_content"],
        line(
            chunk_id="b",
            chunk_scope="content",
            chunk_type="section",
            section_id="SI00000001_SC1_s01",
            content=policy_chunk_text,
            block_ids=["b001"],
            **common,
        ),
    )
    _write(
        files["faq_1350"],
        line(
            chunk_id="c",
            chunk_scope="faq",
            chunk_type="faq_pair",
            faq_id="1",
            content=faq_chunk_text,
        ),
    )
    return {"work24_dir": work24, "faq_dir": faq, "files": files}


def test_check_chunks_passes_when_everything_is_contained(tmp_path):
    args = _chunk_fixture(
        tmp_path, "정책: 합성 정책\n합성 본문 전체", "질의: 합성 질의\n답변: 합성 답변"
    )

    result = check_chunks(**args)

    assert result["ok"] is True, result["errors"]
    assert result["counts"] == {"policy_catalog": 1, "policy_content": 1, "faq_1350": 1}


def test_check_chunks_reports_partial_block_and_answer(tmp_path):
    args = _chunk_fixture(tmp_path, "합성 본문", "질의: 합성 질의\n답변: 합성")

    errors = check_chunks(**args)["errors"]

    assert errors == [
        "SI00000001_SC1_s01/b001: 일부만 담김 (빠진 앞부분 '전체')",
        "1: 답변 일부만 담김 (빠진 앞부분 '답변')",
    ]
