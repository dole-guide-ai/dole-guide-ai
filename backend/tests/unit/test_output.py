"""출력 관문(agent/output.py): 문장 단위로 보내고 다른 언어가 섞인 문장부터 버림."""

from app.agent.output import SentenceStream


def _run(chunks: list[str]) -> tuple[list[str], SentenceStream]:
    stream = SentenceStream()
    sent = [piece for chunk in chunks for piece in stream.feed(chunk)]
    return sent + stream.close(), stream


def test_sends_whole_sentences_and_keeps_text_unchanged() -> None:
    text = "희망 지역을 **인천**으로 저장했어요.\n\n1. 희망 직종\n2. 학력 3.8점도 적을게요."
    chunks = [text[i : i + 3] for i in range(0, len(text), 3)]

    sent, stream = _run(chunks)

    assert "".join(sent) == text == stream.text
    assert not stream.dropped
    assert sent[0] == "희망 지역을 **인천**으로 저장했어요."  # 문장이 끝나야 보냄


def test_drops_leaked_foreign_sentence_and_everything_after() -> None:
    sent, stream = _run(["이제 희망 직종도 말씀해 주세요. на", "пр? No. Korean."])

    assert "".join(sent) == stream.text == "이제 희망 직종도 말씀해 주세요. "
    assert stream.dropped


def test_keeps_latin_program_names_and_numbers() -> None:
    sent, _ = _run(["CAP@·Hi+ 프로그램은 4주 1회 인정돼요. KDT 과정도 돼요."])

    assert "".join(sent) == "CAP@·Hi+ 프로그램은 4주 1회 인정돼요. KDT 과정도 돼요."
