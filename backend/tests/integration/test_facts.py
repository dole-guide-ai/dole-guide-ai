"""내 정보 보기·한 줄 지우기 통합 테스트 (F-31)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

URL = "/accounts/lee/facts"


def _ids(body: dict) -> dict[str, dict]:
    return {item["fact_id"]: item for item in body["items"]}


def test_lee_sees_documents_procedure_and_answers(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    res = client.get(URL, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    items = _ids(body)
    assert items["resume.status"]["value"] == "저장 완료"
    assert not items["procedure.stage"]["is_deletable"]
    credit = items["application.credit"]
    assert credit["group"] == "facts" and credit["is_deletable"]
    assert credit["value"].startswith("희망함")
    assert items["application.notification_method"]["value"] == "휴대전화 문자메시지"
    assert "주민등록번호" in body["not_stored"]


def test_delete_credit_answer_goes_back_to_answer_needed(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    res = client.delete(f"{URL}/application.credit", headers=headers)
    assert res.status_code == 200, res.text
    assert {u["path"] for u in res.json()["updates"]} >= {"/credit/application"}
    assert all(u["status"] == "rejected" for u in res.json()["updates"])

    # 지난 회차 답을 다시 불러오지 않고, 신청서 그 칸이 답변 필요로 남습니다.
    assert "application.credit" not in _ids(client.get(URL, headers=headers).json())
    app = client.get("/accounts/lee/rounds/current/application", headers=headers).json()
    assert app["data"]["credit"]["application"]["value"] is None
    assert app["data"]["credit"]["application"]["status"] == "rejected"
    # 다른 답(통지 방법)은 그대로
    assert app["data"]["notification_method"]["value"] == "sms"


def test_procedure_row_is_409_and_unknown_is_404(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    for fact_id in ("procedure.stage", "resume.status"):
        res = client.delete(f"{URL}/{fact_id}", headers=headers)
        assert res.status_code == 409 and res.json()["code"] == "FACT_NOT_DELETABLE"
    for fact_id in ("nope", "resume.careers.career_001.company_name"):
        assert client.delete(f"{URL}/{fact_id}", headers=headers).status_code == 404
