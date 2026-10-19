# backend/AGENTS.md

공통 규칙은 루트 `AGENTS.md`를 따릅니다. 명령은 이 폴더(`backend/`)에서 실행합니다.

```bash
uv run uvicorn app.main:app --reload
uv run ruff check --fix . && uv run ruff format .
uv run pytest
```
