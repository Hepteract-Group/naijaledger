"""Test-only smoke rule (not registered in production)."""

from naijaledger.anomaly.context import RuleContext
from naijaledger.anomaly.models import FlagDraft


class SmokeEmptyRule:
    """Always returns no drafts — proves the runner wiring."""

    id = "smoke"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        return []
