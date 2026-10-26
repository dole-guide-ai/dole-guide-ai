# AI 평가 세트

모델·프롬프트·규칙표를 바꾸는 PR은 이 평가 결과를 PR 본문에 첨부합니다.

## 실행

```bash
uv run pytest evals -m eval          # 전체
uv run pytest evals -m eval -k procedure   # 일부 시나리오
```

기본 `uv run pytest`에서는 실행되지 않습니다. 실제 LLM을 호출하는 평가는 `.env`에 고른 공급자의 키(`OPENAI_API_KEY`·`UPSTAGE_API_KEY`)가 없으면 건너뜁니다.

## 시나리오 추가 규칙

- `scenarios/<영역>/<시나리오>.json` 한 파일에 한 시나리오. 영역 예: `procedure`(절차 안내), `form_fill`(서류 추출), `grounding`(근거 일치·거절), `masking`(개인정보 차단)
- 실제 개인정보 금지. 이름·연락처·주민등록번호는 합성 값만 씁니다.
- 형식:

```json
{
  "id": "procedure-001",
  "description": "2회차 실업인정일 직전, 재취업활동 1회만 기록된 경우",
  "input": { "messages": ["다음 주에 뭐 해야 돼요?"], "state": {} },
  "expected": { "next_action": "add_job_search_activity", "must_include": ["1회 더"] }
}
```

- 판정은 정답 비교(단계·마감일·추출값)를 먼저 쓰고, 문장 품질처럼 정답이 없는 항목만 LLM 판정을 씁니다.

## 골든셋 (`golden/`)

AI가 바뀔 때마다 같은 문항으로 다시 채점하는 기준 문항 세트입니다. 원본은 `golden/golden_set.csv` 한 파일(507문항, #230에서 100 → 500으로 확장, #257에서 웹 직접 테스트 문제 7개 추가)이고, 설계 원칙·문항 목록은 팀 문서 「실업급여 길잡이 골든셋」에 있습니다.

### 구성 원칙 (500문항 확장 기준, #228·#230)

골든셋 구축 가이드(500개 이상, 일반 케이스 중심 + 엣지 20%, 루브릭 선행, 교차 검수, 결정적 채점 우선, pass^k 게이트, 실패 순환)를 기준으로 삼되, 이 서비스에 맞게 조정했습니다.

- **분포**: 영역 절차 195 · 서류 120 · 근거 120 · 개인정보 65. 방법은 기본(자연스러운 일상 발화) 49% + 변형·엣지(바꿔말하기·경계값·여러턴·공격·범위밖·회귀·파일) 51%. 일반 가이드(80/20)보다 엣지 비중을 높인 것은 의도된 선택입니다 — 행정 숫자·개인정보·부정수급이 걸린 서비스라 실패 비용이 큰 쪽을 두껍게 쟀습니다.
- **출처**: 아직 운영 데이터가 없어 전부 합성입니다(시연 대본, 1350 상담 답변, 고용24 안내, 팀 규칙표 카드). 출시 뒤에는 분기마다 운영 로그에서 50~100문항을 뽑아 교체·추가하고, 낡은 문항을 지웁니다.
- **채점**: 정답을 코드로 확정할 수 있는 항목(기대값·변경금지·꼭포함·개인정보검사)을 먼저 쓰고, LLM 판정(채점기준)은 문장 품질처럼 정답이 없는 항목에만 둡니다. 채택·배포 판단 지표는 pass@k가 아니라 **pass^k**(일관성)입니다.
- **검수**: 기대값이 규칙표 문자열·규칙 함수 결과와 기계적으로 일치하는 문항만 `확정`, 해석이 들어가거나 공식 문구를 못 찾은 문항은 `확인필요`(실패해도 참고로만 집계)입니다. 신규 문항은 작성자 1인 검수 상태이므로, 팀 교차 검수에서 이견이 나오면 `확인필요`로 내리고 채점기준(루브릭)을 보완합니다.
- **오염 방지**: 규칙표 카드 기반 문항(근거 칸에 `규칙표 <ID>`)은 검색 색인에 들어가는 예상 질문(doc2query)과 겹치면 점수가 부풀므로, `uv run python -m scripts.draft_golden_from_rules --check evals/golden/golden_set.csv`로 2-gram 자카드 0.5 미만을 확인합니다(규칙표 CSV 필요, #220).
- **실패 순환**: 실측·운영에서 발견한 버그는 `방법=회귀` 문항으로 들어옵니다(예: 8차 필요 건수 0, 같은 턴 기록 뒤 건수).
- **첨부 파일**: `golden/files/`의 사진 15장은 전부 합성입니다. 새로 만든 6장의 생성 코드는 `scripts/make_golden_files.ps1`(Windows 전용 일회성 도구)입니다.

| 명령 (루트) | 하는 일 |
| --- | --- |
| `pnpm golden:check` | CSV 검사만 (칸 이름·값·첨부 파일). 고칠 곳을 줄 번호와 함께 알려 줌 |
| `pnpm golden:build` | CSV → `scenarios/golden/<영역>/<ID>.json`. 만든 JSON은 저장소에 올리지 않음 |
| `pnpm eval:golden` | 만들기 + 실제 AI로 실행·채점 → `evals/reports/golden-<시각>.md` |
| `pnpm eval:golden:selftest` | 만들기 + 가짜 AI로 채점 코드만 점검. 전 문항이 통과해야 정상 |

- 옵션은 뒤에 붙입니다: `pnpm eval:golden --golden-area=masking`(영역만), `--golden-threshold=0.8`(LLM 판정 기준, 기본 0.7)
- GitHub에서: Actions → `golden-eval` → Run workflow. 결과 표는 실행 화면 Summary에, 보고서는 Artifacts에 남습니다. real 모드는 Secrets `OPENAI_API_KEY`·`UPSTAGE_API_KEY`, Variables `*_PROVIDER`·`AGENT_MODEL`·`EXTRACT_MODEL`·`JUDGE_MODEL`을 씁니다.
- 결과: 통과 · 실패 · 참고 실패(검수 `확인필요` 문항, 실패로 치지 않음) · 판정 건너뜀(키가 없어 LLM 판정만 못 함) · 건너뜀

### 문항 고치기

엑셀이나 구글 시트로 CSV를 열어 고치고 'CSV UTF-8'로 저장한 뒤 `pnpm golden:check`를 실행합니다. 한 칸에 여러 값은 `;`, 여러 번 주고받는 말은 `||`로 나눕니다.

| 열 | 쓰는 법 |
| --- | --- |
| ID · 영역 · 방법 · 검수 | `P-001` · 절차/서류/근거/개인정보 · 기본/경계값/바꿔말하기/여러턴/공격/범위밖/회귀/파일 · 확정/확인필요/보류 |
| 계정 · 상태값 · 활동 | `golden/presets.py`의 이름(park·choi·lee·general1~4 등) · `이름=값; ...`(`seed=park_career` 가능) · `2026-12-08 job_search work24 OO물류; ...` 또는 `없음` |
| 입력 · 첨부 | 사용자 말(`\|\|`로 턴 구분) · `golden/files/`의 파일 이름 |
| 다음할일 · 기대값 · 변경금지 | `schema.NEXT_ACTIONS` 중 하나 · `경로=값`(`!=` 다름, `^=` 로 시작, `*=` 포함, `.length` 개수) · 바뀌면 안 되는 경로 |
| 꼭포함 · 포함금지 · 금지패턴 | 마지막 답에 있어야 할 말 · 어느 답에도 없어야 할 말 · 정규식 |
| 개인정보검사 | 남으면 안 되는 글자. 앞에 `답:`·`저장:`·`모델:`을 붙여 범위를 좁힘(없으면 전체) |
| 근거표시 · 채점기준 · 근거 | 답에 근거 줄이 있어야 하면 `Y` · LLM 판정 기준 문장 · 기대 결과의 출처 |

경로 이름은 프론트 타입과 같습니다: `derived`(DerivedState), `round`(RoundCheckRead), `resume`(ResumeValues), `activities`(RoundActivity[]), `recognition`(RecognitionFormRead), `procedure`(`stage`·`education_done`, 대화로 단계가 넘어가는지 볼 때).

### AI 연결

`golden/adapter.py`의 `run_agent()`만 채우면 됩니다. 문항 입력(상태·시작 데이터·말·첨부)을 받아 `AgentResult`(답 문장, 다음할일, 결과 데이터, 근거 줄)를 돌려주세요. 모델에 보낸 글은 테스트가 gateway 호출을 자동으로 기록해 개인정보 검사에 씁니다. LLM 판정은 `gateway.get_chat_model(role="judge")`를 쓰고(`JUDGE_PROVIDER`·`JUDGE_MODEL`, 비우면 AGENT 설정), 그 공급자 키가 없으면 판정만 건너뜁니다.

## 말하기 평가 (`voice/`)

말하기 버튼의 음성 인식(`STT_MODEL`)을 합성 음성으로 잽니다. 문장 15개(`voice/sentences.csv`: 기본·사투리·군말·느린 말·숫자·날짜)를 TTS로 60대 말투 음성으로 만들고, 같은 음성에 잡음(10dB)을 섞은 버전도 받아써 글자 오류율(CER)과 핵심어 정확도를 냅니다.

```bash
uv run python -m evals.voice.run --tts-model gpt-4o-mini-tts   # 결과: evals/reports/voice-<시각>.md
```

- 합성 음성은 `backend/.cache/voice_eval/`에 두고 다시 써서 두 번째부터는 받아쓰기(30번)만 부릅니다(`--refresh`로 다시 만듦).
- 소리 내는 글(`spoken`, 숫자를 한글로)과 정답(`reference`, 받아쓴 모양)이 따로 있고, 핵심어는 `a|b`로 같은 뜻의 표기를 함께 받습니다.
