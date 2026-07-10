"""Match adjudicators (E6.2) — opinions only; never merge."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from naijaledger.finance.matching import MatchCandidate
from naijaledger.finance.models import Party

MatchOpinion = Literal["same_entity", "different", "uncertain"]


class AdjudicationOpinion(BaseModel):
    opinion: MatchOpinion
    rationale: str
    adjudicator: str
    suggested_survivor_id: UUID | None = None


class MatchAdjudicator(Protocol):
    def adjudicate(
        self,
        left: Party,
        right: Party,
        candidate: MatchCandidate,
    ) -> AdjudicationOpinion: ...


class StubMatchAdjudicator:
    """Deterministic stand-in for CI; no network."""

    def adjudicate(
        self,
        left: Party,
        right: Party,
        candidate: MatchCandidate,
    ) -> AdjudicationOpinion:
        survivor = left if left.created_at <= right.created_at else right
        if candidate.score >= 0.95:
            return AdjudicationOpinion(
                opinion="same_entity",
                rationale=f"stub: score {candidate.score:.3f} >= 0.95",
                adjudicator="stub",
                suggested_survivor_id=survivor.id,
            )
        if candidate.score >= 0.82:
            return AdjudicationOpinion(
                opinion="uncertain",
                rationale=f"stub: score {candidate.score:.3f} in mid band [0.82, 0.95)",
                adjudicator="stub",
                suggested_survivor_id=survivor.id,
            )
        return AdjudicationOpinion(
            opinion="different",
            rationale=f"stub: score {candidate.score:.3f} < 0.82",
            adjudicator="stub",
            suggested_survivor_id=None,
        )


def get_match_adjudicator(name: str = "stub") -> MatchAdjudicator:
    if name == "stub":
        return StubMatchAdjudicator()
    raise ValueError(
        f"unknown match adjudicator {name!r}; live LLM wiring is deferred — use 'stub'"
    )


__all__ = [
    "AdjudicationOpinion",
    "MatchAdjudicator",
    "MatchOpinion",
    "StubMatchAdjudicator",
    "get_match_adjudicator",
]
