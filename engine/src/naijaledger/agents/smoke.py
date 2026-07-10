"""Test-only smoke agent (not a production narrative agent)."""

from __future__ import annotations

from typing import Any

from naijaledger.agents.models import AgentAction, AgentContext


class EchoToolsAgent:
    """Calls list_open_flags once, then finishes — proves the run loop."""

    id = "echo_tools"

    def step(self, ctx: AgentContext, history: list[dict[str, Any]]) -> AgentAction:
        if not history:
            return AgentAction(type="call_tool", tool="list_open_flags", args={"limit": 5})
        return AgentAction(
            type="finish",
            summary="echo_tools completed",
            drafts=[],
        )


class NeverFinishAgent:
    id = "never_finish"

    def step(self, ctx: AgentContext, history: list[dict[str, Any]]) -> AgentAction:
        return AgentAction(type="call_tool", tool="list_open_flags", args={"limit": 1})
