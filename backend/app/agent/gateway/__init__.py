from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import get_settings


def get_chat_model(role: str = "agent") -> BaseChatModel:
    """모든 LLM 호출은 이 게이트웨이를 거칩니다. 엔노이아 전환 시 설정만 바꿉니다."""
    settings = get_settings()
    model = settings.agent_model if role == "agent" else settings.extract_model
    if role == "judge":  # 골든셋 LLM 판정 전용 (evals/golden/judge.py)
        model = settings.judge_model or settings.agent_model
    if settings.llm_provider in ("openai", "ennoia"):
        # 엔노이아가 OpenAI 호환 API라면 llm_base_url만 바꿔 사용합니다.
        return ChatOpenAI(model=model, api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    raise ValueError(f"지원하지 않는 LLM provider: {settings.llm_provider}")
