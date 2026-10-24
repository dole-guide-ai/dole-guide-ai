from app.agent.masking import mask
from app.agent.schemas import AgentState


def preprocess(state: AgentState) -> AgentState:
    """사용자 말에서 개인정보를 가립니다. 이후 단계와 모델은 가린 글만 봅니다."""
    masked, _ = mask(state["message"])
    return {"message": masked}
