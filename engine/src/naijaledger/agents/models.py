"""Agent runtime models (E8.1 / spec 0020)."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Citation(BaseModel):
    kind: str
    subject_type: str | None = None
    subject_id: UUID | None = None
    document_id: UUID | None = None
    label: str
    detail: dict[str, Any] | None = None


class ToolResult(BaseModel):
    ok: bool
    tool: str
    data: Any = None
    error: str | None = None
    citations: list[Citation] = Field(default_factory=list)


class AgentAction(BaseModel):
    type: Literal["call_tool", "finish"]
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    drafts: list[dict[str, Any]] = Field(default_factory=list)


class AgentRunResult(BaseModel):
    run_id: UUID
    agent_id: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    finished: bool
    summary: str | None = None
    drafts: list[dict[str, Any]] = Field(default_factory=list)


class ToolRegistry:
    """Name → tool map (plain class; tools are Protocol instances)."""

    def __init__(self, tools: dict[str, Any] | None = None) -> None:
        self._tools: dict[str, Any] = dict(tools or {})

    def get(self, name: str) -> Any | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def run(self, name: str, ctx: Any, args: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, tool=name, error=f"unknown tool: {name}")
        try:
            result = tool.run(ctx, args)
        except Exception as exc:  # noqa: BLE001 — tools must not crash the run loop
            return ToolResult(ok=False, tool=name, error=str(exc))
        if not isinstance(result, ToolResult):
            return ToolResult(ok=False, tool=name, error="tool returned invalid result")
        return result


def register_tools(tools: list[Any]) -> ToolRegistry:
    mapping: dict[str, Any] = {}
    for tool in tools:
        if tool.name in mapping:
            raise ValueError(f"duplicate tool name: {tool.name}")
        mapping[tool.name] = tool
    return ToolRegistry(mapping)


class AgentContext:
    def __init__(
        self,
        *,
        connection: Any,
        tools: ToolRegistry,
        run_id: UUID,
        graph_client: Any | None = None,
    ) -> None:
        self.connection = connection
        self.tools = tools
        self.run_id = run_id
        self.graph_client = graph_client
