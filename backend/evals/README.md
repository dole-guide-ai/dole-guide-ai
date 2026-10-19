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
