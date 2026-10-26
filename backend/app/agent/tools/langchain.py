"""레지스트리 도구를 LangChain 도구로 바꿉니다 (`model.bind_tools`·`ToolNode`에 바로 씁니다).

`ToolContext`(계정·DB·오늘 날짜)는 턴마다 여기서 묶어 넣습니다. LLM은 입력 모델의 인자만 봅니다.
`ToolError`(권한 밖 칸 등)는 예외로 끝내지 않고 거절 사유를 도구 결과로 LLM에게 돌려줍니다.
"""

from collections.abc import Iterable
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool, ToolException

from app.agent.tools.registry import TOOLS, Tool, ToolContext, ToolError, execute


def _as_langchain(ctx: ToolContext, tool: Tool) -> BaseTool:
    def run(**kwargs: Any) -> dict[str, Any]:
        try:
            return execute(ctx, tool, tool.input_model.model_validate(kwargs))
        except ToolError as exc:
            raise ToolException(str(exc)) from exc

    return StructuredTool.from_function(
        func=run,
        name=tool.name,
        description=tool.description,
        args_schema=tool.input_model,
        handle_tool_error=True,
    )


def as_langchain_tools(ctx: ToolContext, names: Iterable[str]) -> list[BaseTool]:
    """이름 순서대로 LangChain 도구를 만듭니다.

    예: `as_langchain_tools(ctx, TOOLS_BY_PANEL["round"])`
    """
    return [_as_langchain(ctx, TOOLS[name]) for name in names]
