# frontend/AGENTS.md

공통 규칙은 루트 `AGENTS.md`를 따릅니다. 아래 영어 블록은 `next dev`가 자동으로 다시 쓰니 수정하지 않습니다. (요약: Next.js 16은 예전과 다르니 코드를 쓰기 전에 `node_modules/next/dist/docs/`를 확인)

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
