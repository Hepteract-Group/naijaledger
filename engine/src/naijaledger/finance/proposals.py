"""Party match proposals — human-confirmed merges (E6.2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.finance.adjudicators import MatchAdjudicator, StubMatchAdjudicator
from naijaledger.finance.matching import MatchCandidate
from naijaledger.finance.models import Party, PartyMatchProposal
from naijaledger.finance.service import apply_party_merge, get_party

_PROPOSAL_COLUMNS = """
    id, left_party_id, right_party_id, match_score, match_rule, match_reason,
    opinion, opinion_rationale, adjudicator, status, suggested_survivor_id,
    resolved_by, resolved_at, meta, created_at, updated_at
"""


class ProposalNotFoundError(LookupError):
    pass


class ProposalStateError(ValueError):
    pass


def _row_to_proposal(row: Row[Any]) -> PartyMatchProposal:
    mapping = row._mapping
    return PartyMatchProposal(
        id=mapping["id"],
        left_party_id=mapping["left_party_id"],
        right_party_id=mapping["right_party_id"],
        match_score=float(mapping["match_score"]),
        match_rule=mapping["match_rule"],
        match_reason=mapping["match_reason"],
        opinion=mapping["opinion"],
        opinion_rationale=mapping["opinion_rationale"],
        adjudicator=mapping["adjudicator"],
        status=mapping["status"],
        suggested_survivor_id=mapping["suggested_survivor_id"],
        resolved_by=mapping["resolved_by"],
        resolved_at=mapping["resolved_at"],
        meta=mapping["meta"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def get_match_proposal(connection: Connection, proposal_id: UUID) -> PartyMatchProposal:
    try:
        row = connection.execute(
            text(f"SELECT {_PROPOSAL_COLUMNS} FROM party_match_proposals WHERE id = :id"),
            {"id": proposal_id},
        ).one()
    except NoResultFound as exc:
        raise ProposalNotFoundError(str(proposal_id)) from exc
    return _row_to_proposal(row)


def create_match_proposal(
    connection: Connection,
    candidate: MatchCandidate,
    *,
    adjudicator: MatchAdjudicator | None = None,
) -> PartyMatchProposal:
    left = get_party(connection, candidate.left_id)
    right = get_party(connection, candidate.right_id)
    if left.merged_into_id is not None or right.merged_into_id is not None:
        raise ProposalStateError("cannot propose match involving an already-merged party")
    judge = adjudicator or StubMatchAdjudicator()
    opinion = judge.adjudicate(left, right, candidate)
    row = connection.execute(
        text(
            f"""
            INSERT INTO party_match_proposals (
                left_party_id, right_party_id, match_score, match_rule, match_reason,
                opinion, opinion_rationale, adjudicator, status, suggested_survivor_id, meta
            ) VALUES (
                :left_party_id, :right_party_id, :match_score, :match_rule, :match_reason,
                :opinion, :opinion_rationale, :adjudicator, 'pending', :suggested_survivor_id,
                CAST(:meta AS jsonb)
            )
            RETURNING {_PROPOSAL_COLUMNS}
            """
        ),
        {
            "left_party_id": left.id,
            "right_party_id": right.id,
            "match_score": candidate.score,
            "match_rule": candidate.rule,
            "match_reason": candidate.reason,
            "opinion": opinion.opinion,
            "opinion_rationale": opinion.rationale,
            "adjudicator": opinion.adjudicator,
            "suggested_survivor_id": opinion.suggested_survivor_id,
            "meta": None,
        },
    ).one()
    return _row_to_proposal(row)


def list_pending_match_proposals(
    connection: Connection,
    *,
    limit: int = 50,
) -> list[PartyMatchProposal]:
    rows = connection.execute(
        text(
            f"""
            SELECT {_PROPOSAL_COLUMNS}
            FROM party_match_proposals
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).all()
    return [_row_to_proposal(row) for row in rows]


def confirm_match_proposal(
    connection: Connection,
    proposal_id: UUID,
    *,
    confirmed_by: str,
    survivor_id: UUID,
    merged_id: UUID,
) -> Party:
    proposal = get_match_proposal(connection, proposal_id)
    if proposal.status != "pending":
        raise ProposalStateError(f"proposal is {proposal.status}, not pending")
    pair = {proposal.left_party_id, proposal.right_party_id}
    if {survivor_id, merged_id} != pair:
        raise ProposalStateError("survivor/merged must be exactly the proposal party pair")
    survivor = apply_party_merge(
        connection,
        survivor_id=survivor_id,
        merged_id=merged_id,
    )
    connection.execute(
        text(
            """
            UPDATE party_match_proposals
            SET status = 'confirmed',
                resolved_by = :resolved_by,
                resolved_at = now(),
                updated_at = now()
            WHERE id = :id
            """
        ),
        {"id": proposal_id, "resolved_by": confirmed_by},
    )
    return survivor


def reject_match_proposal(
    connection: Connection,
    proposal_id: UUID,
    *,
    rejected_by: str,
) -> PartyMatchProposal:
    proposal = get_match_proposal(connection, proposal_id)
    if proposal.status != "pending":
        raise ProposalStateError(f"proposal is {proposal.status}, not pending")
    connection.execute(
        text(
            """
            UPDATE party_match_proposals
            SET status = 'rejected',
                resolved_by = :resolved_by,
                resolved_at = now(),
                updated_at = now()
            WHERE id = :id
            """
        ),
        {"id": proposal_id, "resolved_by": rejected_by},
    )
    return get_match_proposal(connection, proposal_id)
