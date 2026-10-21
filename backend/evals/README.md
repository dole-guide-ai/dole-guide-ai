# AI 평가 세트

모델·프롬프트·규칙표를 바꾸는 PR은 이 평가 결과를 PR 본문에 첨부합니다.

## 실행

```bash
uv run pytest evals -m eval          # 전체
uv run pytest evals -m eval -k procedure   # 일부 시나리오
```

기본 `uv run pytest`에서는 실행되지 않습니다. 실제 LLM을 호출하는 평가는 `.env`의 `LLM_API_KEY`가 없으면 건너뜁니다.

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

AI가 바뀔 때마다 같은 문항으로 다시 채점하는 기준 문항 세트입니다. 원본은 `golden/golden_set.csv` 한 파일이고, 설계 원칙·문항 목록은 팀 문서 「실업급여 길잡이 골든셋」에 있습니다.

| 명령 (루트) | 하는 일 |
| --- | --- |
| `pnpm golden:check` | CSV 검사만 (칸 이름·값·첨부 파일). 고칠 곳을 줄 번호와 함께 알려 줌 |
| `pnpm golden:build` | CSV → `scenarios/golden/<영역>/<ID>.json`. 만든 JSON은 저장소에 올리지 않음 |

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

경로 이름은 프론트 타입과 같습니다: `derived`(DerivedState), `round`(RoundCheckRead), `resume`(ResumeValues), `activities`(RoundActivity[]), `recognition`(RecognitionFormRead).
