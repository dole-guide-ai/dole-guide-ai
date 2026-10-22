import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import FORMAT, KstFormatter, RequestIdFilter
from app.core.request_id import RequestIdMiddleware, current_request_id


def _format(record: logging.LogRecord) -> str:
    RequestIdFilter().filter(record)
    return KstFormatter(FORMAT).format(record)


def _record(created: float) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "count=%s", (3,), None)
    record.created = created
    return record


def test_log_time_is_kst_regardless_of_server_timezone() -> None:
    # 2026-10-22 08:00:00 UTC == 17:00 KST
    line = _format(_record(1792656000.0))

    assert line.startswith("2026-10-22T17:00:00.000+09:00 INFO [-] app.test count=3")


def test_log_line_carries_current_request_id() -> None:
    token = current_request_id.set("abc12345-req")
    try:
        line = _format(_record(1792656000.0))
    finally:
        current_request_id.reset(token)

    assert "[abc12345-req]" in line


def test_middleware_sets_request_id_only_during_request() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    seen: list[str] = []

    @app.get("/ping")
    def ping() -> dict[str, str]:
        seen.append(current_request_id.get())
        return {}

    res = TestClient(app).get("/ping", headers={"X-Request-ID": "abc12345-req"})

    assert seen == ["abc12345-req"] == [res.headers["X-Request-ID"]]
    assert current_request_id.get() == "-"


def test_uvicorn_error_logs_use_same_format() -> None:
    from app.core.logging import UVICORN_ERROR_LOGGER, setup_logging

    setup_logging()
    uvicorn_error = logging.getLogger(UVICORN_ERROR_LOGGER)

    assert uvicorn_error.propagate is False
    [handler] = uvicorn_error.handlers
    assert isinstance(handler.formatter, KstFormatter)
    assert any(isinstance(f, RequestIdFilter) for f in handler.filters)
