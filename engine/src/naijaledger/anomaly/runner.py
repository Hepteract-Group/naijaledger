"""Anomaly rule protocol + runner (E7.1)."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection

from naijaledger.anomaly.context import RuleContext, load_rule_context
from naijaledger.anomaly.models import FlagDraft
from naijaledger.anomaly.service import upsert_open_flag


class AnomalyRule(Protocol):
    id: str

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]: ...


class RunResult(BaseModel):
    rules_run: list[str] = Field(default_factory=list)
    drafts: int = 0
    upserted: int = 0


def run_anomaly_rules(
    connection: Connection,
    rules: list[AnomalyRule],
    *,
    rule_ids: list[str] | None = None,
    ctx: RuleContext | None = None,
) -> RunResult:
    selected = [rule for rule in rules if rule_ids is None or rule.id in rule_ids]
    context = ctx if ctx is not None else load_rule_context(connection)
    result = RunResult(rules_run=[rule.id for rule in selected])
    for rule in selected:
        drafts = rule.evaluate(context)
        result.drafts += len(drafts)
        for draft in drafts:
            if upsert_open_flag(connection, draft) is not None:
                result.upserted += 1
    return result


def production_rules() -> list[AnomalyRule]:
    """Finance red-flag rules registered for scheduled runs (excludes smoke)."""
    return []
