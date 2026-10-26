"""말하기(음성 인식) 평가: 합성 음성을 서비스와 같은 경로(gateway.transcribe_audio)로 받아써 잽니다.

    uv run python -m evals.voice.run --tts-model <TTS 모델> [--refresh]

- 문장은 `sentences.csv`(합성 문장, 개인정보 없음). 소리 내는 글(spoken)과 받아쓴 정답(reference)이
  따로 있어 "이천십일"을 "2011"로 받아써도 틀리지 않습니다.
- 문장마다 TTS로 60대 말투 음성을 만들고(사투리 문장은 사투리 억양), 잡음을 섞은 버전도 만듭니다.
  만든 음성은 `backend/.cache/voice_eval/`에 두고 다시 쓰므로 두 번째부터는 받아쓰기만 부릅니다.
- 지표: 글자 오류율(CER, 띄어쓰기·문장부호 빼고 편집 거리 / 정답 글자 수), 핵심어 정확도
  (keywords의 각 묶음 `a|b` 중 하나가 받아쓴 글에 있는 비율). 결과는 `evals/reports/voice-*.md`.
- 음성 인식 모델은 서비스 설정(STT_MODEL)을 그대로 씁니다. TTS 모델은 평가에만 쓰므로
  인자로 받습니다.
"""

import argparse
import csv
import hashlib
import io
import re
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import openai

from app.agent import gateway
from app.core.config import get_settings

HERE = Path(__file__).resolve().parent
SENTENCES = HERE / "sentences.csv"
CACHE = HERE.parents[1] / ".cache" / "voice_eval"
REPORTS = HERE.parent / "reports"
# 잡음 버전의 신호 대 잡음비(dB). 10dB는 TV를 켜 둔 방 정도입니다.
NOISE_SNR_DB = 10
NOISE_SEED = 7
VOICE = "onyx"
STYLE_INSTRUCTIONS = {
    "사투리": "60대 남성이 경상도 사투리 억양으로 천천히, 조금 투박하게 말합니다.",
    "느린말": "70대 어르신이 아주 천천히 또박또박 말합니다.",
}
DEFAULT_INSTRUCTIONS = "60대 남성이 평소 대화하듯 조금 느리게 말합니다."
_IGNORED = re.compile(r"[\s.,?!…·'\"]")


@dataclass
class Row:
    id: str
    style: str
    spoken: str
    reference: str
    keywords: list[list[str]]


def load_rows() -> list[Row]:
    with SENTENCES.open(encoding="utf-8") as f:
        return [
            Row(
                r["id"],
                r["style"],
                r["spoken"],
                r["reference"],
                [group.split("|") for group in r["keywords"].split(";") if group],
            )
            for r in csv.DictReader(f)
        ]


def cer(reference: str, hypothesis: str) -> float:
    """띄어쓰기·문장부호를 뺀 글자 편집 거리 / 정답 글자 수."""
    ref, hyp = _IGNORED.sub("", reference), _IGNORED.sub("", hypothesis)
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        current = [i]
        for j, h in enumerate(hyp, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (r != h)))
        previous = current
    return previous[-1] / max(len(ref), 1)


def keyword_hits(row: Row, hypothesis: str) -> tuple[int, int]:
    text = _IGNORED.sub("", hypothesis)
    hits = sum(any(_IGNORED.sub("", k) in text for k in group) for group in row.keywords)
    return hits, len(row.keywords)


def speech(client: openai.OpenAI, row: Row, tts_model: str, refresh: bool) -> Path:
    instructions = STYLE_INSTRUCTIONS.get(row.style, DEFAULT_INSTRUCTIONS)
    # 모델·목소리·말투·문장이 바뀌면 다른 파일이 되어 예전 녹음을 다시 쓰지 않습니다.
    key = "|".join((tts_model, VOICE, instructions, row.spoken))
    path = CACHE / f"{row.id}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]}.wav"
    if refresh or not path.exists():
        audio = client.audio.speech.create(
            model=tts_model,
            voice=VOICE,
            input=row.spoken,
            instructions=instructions,
            response_format="wav",
        )
        path.write_bytes(audio.content)
    return path


def with_noise(path: Path) -> bytes:
    """같은 음성에 흰 잡음을 섞은 wav (NOISE_SNR_DB)."""
    with wave.open(str(path), "rb") as source:
        params = source.getparams()
        samples = np.frombuffer(source.readframes(params.nframes), dtype=np.int16).astype(float)
    power = np.mean(samples**2) or 1.0
    noise = np.random.default_rng(NOISE_SEED).normal(
        0, np.sqrt(power / 10 ** (NOISE_SNR_DB / 10)), samples.shape
    )
    mixed = np.clip(samples + noise, -32768, 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        # TTS wav는 스트리밍용이라 헤더 길이가 최댓값입니다. 길이는 빼고 형식만 옮깁니다.
        target.setnchannels(params.nchannels)
        target.setsampwidth(params.sampwidth)
        target.setframerate(params.framerate)
        target.writeframes(mixed.tobytes())
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tts-model", required=True, help="합성 음성을 만들 TTS 모델")
    parser.add_argument("--refresh", action="store_true", help="저장한 합성 음성을 다시 만들기")
    args = parser.parse_args()
    settings = get_settings()
    CACHE.mkdir(parents=True, exist_ok=True)
    client = openai.OpenAI(api_key=settings.openai_api_key)

    lines = [
        f"# 말하기 평가 ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        f"음성 인식 `{settings.stt_model}` · TTS `{args.tts_model}` · 잡음 {NOISE_SNR_DB}dB",
        "",
        "| ID | 말투 | 조건 | CER | 핵심어 | 받아쓴 글 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    totals: dict[str, list[float]] = {"깨끗": [], "잡음": []}
    hits_total: dict[str, list[int]] = {"깨끗": [0, 0], "잡음": [0, 0]}
    for row in load_rows():
        clean = speech(client, row, args.tts_model, args.refresh)
        for condition, audio in (("깨끗", clean.read_bytes()), ("잡음", with_noise(clean))):
            text = gateway.transcribe_audio(audio, f"{row.id}.wav")
            error = cer(row.reference, text)
            hits, total = keyword_hits(row, text)
            totals[condition].append(error)
            hits_total[condition][0] += hits
            hits_total[condition][1] += total
            lines.append(
                f"| {row.id} | {row.style} | {condition} | {error:.0%} | {hits}/{total} | {text} |"
            )
    lines += ["", "| 조건 | 평균 CER | 핵심어 정확도 |", "| --- | --- | --- |"]
    for condition, errors in totals.items():
        hit, total = hits_total[condition]
        lines.append(f"| {condition} | {np.mean(errors):.1%} | {hit}/{total} ({hit / total:.0%}) |")
    REPORTS.mkdir(exist_ok=True)
    report = REPORTS / f"voice-{datetime.now():%Y%m%d-%H%M%S}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"보고서: {report}")
    print("\n".join(lines[-4:]))


if __name__ == "__main__":
    main()
