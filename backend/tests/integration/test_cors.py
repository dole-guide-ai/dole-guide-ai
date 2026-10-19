import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

PREVIEW_REGEX = r"^https://dole-guide-[a-z0-9-]+-team\.vercel\.app$"


def make_client() -> TestClient:
    # main.py와 같은 방식으로 CORS를 붙인 최소 앱으로 정규식 동작만 확인합니다.
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://dole-guide-ai.vercel.app"],
        allow_origin_regex=PREVIEW_REGEX,
        allow_methods=["*"],
    )
    app.get("/ping")(lambda: {"ok": True})
    return TestClient(app)


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        ("https://dole-guide-ai.vercel.app", True),
        ("https://dole-guide-j83bvlf4h-team.vercel.app", True),
        ("https://dole-guide-ai-git-feat-34-backend-deploy-team.vercel.app", True),
        ("https://evil.example.com", False),
        ("https://dole-guide-ai-abc123-team.vercel.app.evil.com", False),
        ("https://dole-guide-ai-abc123-other.vercel.app", False),
    ],
)
def test_cors_allows_only_configured_origins(origin: str, allowed: bool) -> None:
    res = make_client().get("/ping", headers={"Origin": origin})

    assert (res.headers.get("access-control-allow-origin") == origin) is allowed
