"""에이전트가 부르는 도구 (AI 설계 6장, `.claude/rules/ai.md`).

도구는 서비스 함수를 얇게 감쌉니다. 계산·검증·저장은 서비스와 규칙 함수가 하고, 도구는 입력 모양을
정하고 결과를 LLM이 읽을 모양으로 돌려줄 뿐입니다. 그래프 없이도 `run_tool`로 바로 부를 수 있습니다.

- 이름은 `동사_명사`, 입력은 Pydantic 모델입니다(LangChain `StructuredTool`로 바꿔 붙이기 쉽게).
- 계정·오늘 날짜는 LLM 인자로 받지 않고 `ToolContext`로 넣습니다.
- 쓰기 도구는 지금 질문이 다루는 칸(`ToolContext.allowed_paths`)만 씁니다. 상태·회차·절차 날짜·
  user_profiles는 도구로 쓰지 않고, 본인 답변 칸은 `record_user_answer`로만 씁니다.
- 패널(서브그래프)마다 쓸 수 있는 도구를 3~4개로 제한합니다(`TOOLS_BY_PANEL`, AI 설계 6.3).
"""

from app.agent.tools.registry import TOOLS, TOOLS_BY_PANEL, Tool, ToolContext, ToolError, run_tool

__all__ = ["TOOLS", "TOOLS_BY_PANEL", "Tool", "ToolContext", "ToolError", "run_tool"]
