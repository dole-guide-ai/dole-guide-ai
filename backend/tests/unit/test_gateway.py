from app.agent import gateway


def test_fake_llm_replaces_gateway_model(fake_llm) -> None:
    fake_llm(["안녕하세요"])

    reply = gateway.get_chat_model().invoke("테스트")

    assert reply.content == "안녕하세요"
