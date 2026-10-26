# AI 설계 V1 — 조합본

#176에서 팀원이 각자 만든 설계(PR 5개)를 비교해, 가장 좋은 부분을 하나로 합친 브랜치입니다.

- 조천산: #220 (`feat/#176-ai-explore`) — 서비스 통합 그래프·하이브리드 검색·팀 규칙표
- 이민수: #214~#217 (`feat/#176-ai-minsoo-*`) — 규칙 코드·날짜·개인정보·프롬프트 원칙·평가 도구

## 조합 기준

| 영역 | 채택 | 근거 |
| --- | --- | --- |
| 그래프·화면 연결 | 조천산 | 실제 채팅 서비스(SSE·패널·되묻기 interrupt)에 연결된 유일한 설계. 라우팅 워크플로: preprocess → load_context → route_turn → attach_knowledge → call_model ⇄ run_tools → finish |
| 라우팅 | 조천산 | 규칙 우선, 못 정할 때만 LLM 분류 → 보통 턴은 분류 호출 0회 |
| 근거·검색 | 조천산 | 팀 규칙표 636카드 + 정책·FAQ 청크, 단어+벡터 하이브리드(RRF). hit@3 0.59 → 0.89. 기본 inject(미리 붙이기, lookup_rules 도구 제거)라 보통 턴 AI 호출 1회 |
| 회차·건수 계산 | 팀 공용 `rules/rounds` + 조천산 load_context(DB 기준) | 이민수 rules 브랜치가 고친 반복수급자 규칙·8차+ "7일마다 1건" 버그픽스 포함 |
| 날짜 변환 | 이민수 `rules/dates.py` | 조천산 `rules/days.py`보다 표현 폭이 넓음("작년 3월 20일", "삼월", 과거로 보정). days.py의 "N일 전"을 dates.py로 합치고 days.py는 삭제. `record_activity` 도구가 이 모듈을 씀 |
| 개인정보 가리기 | 이민수 보강판 `agent/input/pii.py` | 주민번호 뒷자리만, 점·공백 구분 번호, 한글 섞인 이메일, 문장 끝 이름 등 추가 패턴. 조천산 preprocess(0등급 차단·1등급 가리기)가 그대로 사용 |
| 사진 입력 | 이민수 `IMAGE_MODE`(off·vision·transcribe, 기본 off) | vision은 call_model에서 모델 입력에만 붙이고 체크포인트에 남기지 않음. transcribe는 preprocess에서 받아쓴 글을 가린 뒤 상태에 넣음. 사진이 아닌 파일은 보내지 않음 |
| 프롬프트 | 조천산 패널 프롬프트 + 이민수 v2 원칙 | base.md에 추가: 같은 날 1건 인정 안내, 기록한 턴은 도구 결과 건수로 말하기, 가려진 값 복원 금지 |
| 기록 직후 건수 | 이민수 수정의 이식 | `record_activity`가 기록 뒤 회차 점검(`round_after`)을 함께 돌려줘, 상황(facts)의 기록 전 숫자를 그대로 말하는 문제를 막음 |
| 평가 도구 | 둘 다 | 조천산: 실서비스 러너·샤딩(`--golden-shard i/n`)·pass^k·LangSmith. 이민수: 판정 단계 캐시·`--golden-judge off`·비용(토큰·시간) 표 |

## 이 브랜치에서 뺀 것

- 이민수 `turn_graph`(6노드, JSON 한 번 답) 흐름과 `services/agent_turn.py`: 그래프를 하나로 쓰기 위해 제거. 골든셋도 실서비스 러너로 통일
- 이민수 `RETRIEVAL_MODE`(none·keyword·vector·hybrid)와 그 구현: 조천산 하이브리드 검색(knowledge 서비스)으로 대체
- 이민수 `DATE_PARSING`(ai·code) 설정: 이 구조에서 날짜는 항상 코드가 바꾸므로 설정이 필요 없음
- 조천산 `rules/days.py`: `rules/dates.py`로 합침

남긴 이민수 규칙 모듈 중 `rules/situation.py`·`rules/facts.py`·`rules/situation_cards.py`는 상태값(dict) 기반 계산·사실 문장으로, 지금 그래프는 DB 기준 load_context를 쓰므로 직접 쓰이지는 않습니다. 데모 상태 계산·사실 문장 대안으로 남겨 두었고, 필요 없다고 판단되면 지워도 됩니다.

## 기본 설정

| 설정 | 기본값 |
| --- | --- |
| `RULE_CARDS_MODE` | inject |
| `RETRIEVAL_SYNONYMS` / `RETRIEVAL_MIN_SIMILARITY` / `RETRIEVAL_GUIDE_LIMIT` | true / 0.50 / 2 |
| `IMAGE_MODE` | off (사진이 외부 모델로 나가므로 쓰는 환경에서만 켬) |

보통 턴 AI 호출: 라우팅 규칙이 정하면 **1회**(답 모델). 분류가 필요하면 +1, 도구 루프는 상한 4회.

## 확인

- `uv run pytest tests`: 498개 통과 (unit 351 + integration)
- 프론트 `pnpm lint`·`pnpm typecheck`·`pnpm test`: 162개 통과

## 골든셋 측정 (2026-10-26, 조합 뒤)

측정 조건이 두 사람의 기존 수치와 달라 **그 수치들과 직접 견주지 않습니다.**

- gpt-5.4-mini, 골든셋 100문항(팀 수정 반영본), `--golden-judge=off`(판정 LLM 끔, 규칙 채점만), 4조각 병렬(한 번에 약 1분)
- 검색은 단어(BM25)+구어 사전만: 이 측정 환경에 Upstage 키가 없어 벡터 임베딩 없이 색인(조천산 하이브리드 측정 조건보다 불리)
- 첨부 파일 문항 9개는 실서비스 러너가 아직 파일 입력을 받지 않아 건너뜀

| 단계 | 규칙 채점 통과(통과+판정 대기) | 실패 |
| --- | --- | --- |
| 합친 직후 | 62/91 (68%) | 29 |
| 프롬프트 보강(저장 안내·민감 사정·서비스 사실) | 70/91 (77%) | 20 |
| + 회차 상황 카드(facts.round_rules) | 71/91 (78%) | 20 |

마지막 실행 기준 영역별 실패: 절차 15 · 근거 5 · 개인정보 0 · 서류 0.

남은 실패의 원인 (다음 작업):

- 대부분 규칙표 카드 검색 miss(증빙 이름, 신청서 마감 "17시", 65세 이상 "방문" 신청): 벡터+예상 질문이 있는 환경(hit@3 0.89)에서 재측정 필요
- 사실 거절 문구(G-002·G-016 "사실대로")와 가지 않은 면접 기록 거절(G-007): 프롬프트·도구 거절 규칙 추가 필요
- LLM 판정을 켠 최종 점수는 팀이 설정(판정 모델 gpt-4.1)을 정한 뒤 1회 측정 권장
