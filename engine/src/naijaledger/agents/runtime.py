"""Agent run loop (E8.1)."""

from __future__ import annotations

from typing import Any, Protocol

from naijaledger.agents.models import AgentAction, AgentContext, AgentRunResult


class Agent(Protocol):
    id: str

    def step(self, ctx: AgentContext, history: list[dict[str, Any]]) -> AgentAction: ...


def run_agent(
    agent: Agent,
    ctx: AgentContext,
    *,
    max_steps: int = 8,
) -> AgentRunResult:
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")

    history: list[dict[str, Any]] = []
    drafts: list[dict[str, Any]] = []
    summary: str | None = None
    finished = False

    for _ in range(max_steps):
        action = agent.step(ctx, history)
        if action.type == "finish":
            finished = True
            summary = action.summary
            drafts = list(action.drafts)
            history.append({"type": "finish", "summary": summary, "drafts": drafts})
            break

        tool_name = action.tool or ""
        result = ctx.tools.run(tool_name, ctx, action.args)
        history.append(
            {
                "type": "call_tool",
                "tool": tool_name,
                "args": action.args,
                "result": result.model_dump(mode="json"),
            }
        )

    return AgentRunResult(
        run_id=ctx.run_id,
        agent_id=agent.id,
        steps=history,
        finished=finished,
        summary=summary,
        drafts=drafts,
    )
