# AI 평가 세트

모델·프롬프트·규칙표를 바꾸는 PR은 이 평가 결과를 PR 본문에 첨부합니다.

## 실행

```bash
uv run pytest evals -m eval          # 전체
uv run pytest evals -m eval -k procedure   # 일부 시나리오
```

기본 `uv run pytest`에서는 실행되지 않습니다. 실제 LLM을 호출하는 평가는 `.env`에 고른 공급자의 키(`OPENAI_API_KEY`·`UPSTAGE_API_KEY`)나 `AGENT_MODEL`이 없으면 건너뜁니다.

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
| `pnpm eval:golden` | 만들기 + 실제 AI로 실행·채점 → `evals/reports/golden-<시각>.md` |
| `pnpm eval:golden:selftest` | 만들기 + 가짜 AI로 채점 코드만 점검. 100개 모두 통과해야 정상 |

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

경로 이름은 프론트 타입과 같습니다: `derived`(DerivedState), `round`(RoundCheckRead), `resume`(ResumeValues), `activities`(RoundActivity[]), `recognition`(RecognitionFormRead).

### AI 연결

`golden/adapter.py`의 `run_agent()`가 실제 대화 턴(`golden/real.py`, `services/chat`)으로 문항을 돌립니다. 문항마다 새 방문자로 시연 계정에 입장해 말 하나마다 턴을 돌리고, 답 문장 · 근거 줄 · 계정 상태(derived · resume · round · recognition)를 `AgentResult`로 돌려준 뒤 방문자를 지웁니다. 오늘 날짜는 프리셋의 `demo_today`입니다.

- 건너뛰는 문항(보고서에 이유가 남음): 가상 프리셋 계정(general2 등), 상태값 덮어쓰기, 활동 지정, 모델 설정(`AGENT_MODEL` · 키) 없음
- 모델에 보낸 글은 테스트가 gateway 호출을 자동으로 기록해 개인정보 검사에 씁니다.
- LLM 판정은 `gateway.get_chat_model(role="judge")`를 쓰고(`JUDGE_PROVIDER`·`JUDGE_MODEL`, 비우면 AGENT 설정), 그 공급자 키가 없으면 판정만 건너뜁니다.

## 보안 · 일상 질문 시나리오 (`scenarios/security` · `scenarios/small_talk`)

`test_agent_scenarios.py`가 실제 대화 턴으로 돌립니다. 기대값: `no_form_update`, `forbidden_forms`, `forbidden_paths`, `must_include`, `must_not_include`, `no_pii_in_reply`, `never_seen`(모델 입력 · 답 어디에도 없음), `max_llm_calls`(고정 경로는 0). 보안 시나리오는 실제 모델이 필요합니다. 기준: 공격 성공 0건, 정상 질문 오탐률은 보고서에 기록(노션 「AI 설계」 5-2).

## RAG 평가 (`rag/`)

노션 「RAG 기반 하이브리드 검색 시스템 기술 설계 (복사본)」 7절이 기준입니다. 결과는 노션 7.3(임베딩) · 7.4(리랭커) 표에 옮깁니다.

```bash
pnpm rag:load                  # 근거 자료 적재 (backend/data/knowledge/chunks/*.jsonl, 팀원에게 받아 넣기)
pnpm rag:build-set             # 질문셋 rag/rag_set.jsonl 만들기 (EXTRACT 모델 필요)
pnpm eval:rag                  # test 질문 검색 지표 → reports/rag-*.md
pnpm eval:rag -- --rag-reranker --rag-split dev   # 리랭커 켬도 같이, dev 쪽
```

- 질문셋: FAQ 말투 바꾸기(`faq_paraphrase`) + 정책 본문 질문 생성(`generated`) + 답 없는 질문(`unanswerable`). 질문 ID 해시로 dev 80% / test 20%. 자동 생성 질문은 무작위 20%를 사람이 검수해 `reviewed: true`로 바꿉니다.
- 검색 지표: Recall@5 · MRR@10 · nDCG@10(답 있는 질문), '찾지 못함' 비율(답 없는 질문), 지연 평균 · p95.
- 임베딩 비교: 후보마다 `pnpm rag:load -- --model <모델> --provider <공급자>`로 적재하고, `EMBEDDING_MODEL`을 바꿔 `pnpm eval:rag`를 돌려 보고서를 견줍니다.
- 생성 품질(RAGAS): `uv sync --extra rageval` 후 `uv run python -m evals.rag.ragas_eval` → faithfulness · answer_relevancy · context_precision · context_recall
- AutoRAG(오프라인 실험 전용): `uv run python -m evals.rag.autorag_export`로 corpus · qa parquet를 만들고, 별도 가상환경에서 `rag/autorag.yaml`로 돌립니다. 서비스 의존성에는 넣지 않습니다.
