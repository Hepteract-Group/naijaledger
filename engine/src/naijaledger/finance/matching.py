"""Deterministic + probabilistic party matching (E6.1)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from naijaledger.finance.models import Party

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
_SUFFIXES = frozenset(
    {
        "ltd",
        "limited",
        "plc",
        "nig",
        "nigeria",
        "co",
        "company",
        "and",
        "amp",
        "inc",
        "corp",
        "corporation",
        "llc",
    }
)
_STRONG_ID_KEYS = frozenset({"rc", "cac", "tin", "ocds_id"})
PROBABILISTIC_THRESHOLD = 0.82


class MatchCandidate(BaseModel):
    left_id: UUID
    right_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    rule: Literal["deterministic", "probabilistic"]


def _collapse_initial_tokens(tokens: list[str]) -> list[str]:
    collapsed: list[str] = []
    initials: list[str] = []
    for token in tokens:
        if len(token) == 1:
            initials.append(token)
            continue
        if initials:
            collapsed.append("".join(initials))
            initials = []
        collapsed.append(token)
    if initials:
        collapsed.append("".join(initials))
    return collapsed


def normalize_party_name(name: str) -> str:
    lowered = name.lower().strip()
    cleaned = _PUNCT_RE.sub(" ", lowered)
    tokens = [token for token in _SPACE_RE.split(cleaned) if token and token not in _SUFFIXES]
    return " ".join(_collapse_initial_tokens(tokens))


def _identifier_pairs(identifiers: dict[str, Any]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for key, value in identifiers.items():
        key_l = key.lower()
        if key_l in _STRONG_ID_KEYS and value is not None and str(value).strip():
            pairs.add((key_l, str(value).strip().lower()))
        if key_l == "identifier" and isinstance(value, dict):
            scheme = value.get("scheme")
            ident = value.get("id")
            if scheme is not None and ident is not None:
                pairs.add(
                    (
                        f"scheme:{str(scheme).strip().lower()}",
                        str(ident).strip().lower(),
                    )
                )
    return pairs


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    return len(intersection) / len(union)


def _prefix_bonus(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if len(shorter) < 6:
        return 0.0
    return 1.0 if longer.startswith(shorter) else 0.0


def score_party_pair(left: Party, right: Party) -> MatchCandidate | None:
    if left.id == right.id:
        return None
    if left.party_type != right.party_type:
        return None
    if left.merged_into_id is not None or right.merged_into_id is not None:
        return None

    left_norm = normalize_party_name(left.canonical_name)
    right_norm = normalize_party_name(right.canonical_name)
    if left_norm and left_norm == right_norm:
        return MatchCandidate(
            left_id=left.id,
            right_id=right.id,
            score=1.0,
            reason="deterministic:normalized_name",
            rule="deterministic",
        )

    left_ids = _identifier_pairs(left.identifiers)
    right_ids = _identifier_pairs(right.identifiers)
    shared = left_ids & right_ids
    if shared:
        key, _value = next(iter(shared))
        return MatchCandidate(
            left_id=left.id,
            right_id=right.id,
            score=1.0,
            reason=f"deterministic:identifier:{key}",
            rule="deterministic",
        )

    jaccard = _token_jaccard(left_norm, right_norm)
    prefix = _prefix_bonus(left_norm, right_norm)
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    score = max((0.7 * jaccard) + (0.3 * prefix), sequence)
    if score < PROBABILISTIC_THRESHOLD:
        return None
    return MatchCandidate(
        left_id=left.id,
        right_id=right.id,
        score=round(score, 3),
        reason="probabilistic:similarity",
        rule="probabilistic",
    )
