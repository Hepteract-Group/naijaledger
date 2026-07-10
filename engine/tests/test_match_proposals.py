import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from naijaledger.finance.adjudicators import StubMatchAdjudicator
from naijaledger.finance.matching import MatchCandidate, score_party_pair
from naijaledger.finance.models import PartyCreate
from naijaledger.finance.proposals import (
    ProposalStateError,
    confirm_match_proposal,
    create_match_proposal,
    list_pending_match_proposals,
    reject_match_proposal,
)
from naijaledger.finance.service import create_party, get_party


def test_stub_adjudicator_mid_band_uncertain() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from naijaledger.finance.models import Party

    now = datetime.now(tz=UTC)
    left = Party(
        id=uuid4(),
        party_type="company",
        canonical_name="A",
        aliases=[],
        identifiers={},
        address=None,
        merged_into_id=None,
        meta=None,
        created_at=now,
        updated_at=now,
    )
    right = Party(
        id=uuid4(),
        party_type="company",
        canonical_name="B",
        aliases=[],
        identifiers={},
        address=None,
        merged_into_id=None,
        meta=None,
        created_at=now,
        updated_at=now,
    )
    candidate = MatchCandidate(
        left_id=left.id,
        right_id=right.id,
        score=0.88,
        reason="probabilistic:similarity",
        rule="probabilistic",
    )
    opinion = StubMatchAdjudicator().adjudicate(left, right, candidate)
    assert opinion.opinion == "uncertain"


def test_proposal_confirm_merges(db_connection) -> None:
    left = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Gamma Logistics Ltd"),
    )
    right = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Gamma Logistics Limited"),
    )
    candidate = score_party_pair(left, right)
    assert candidate is not None

    proposal = create_match_proposal(db_connection, candidate)
    assert proposal.status == "pending"
    assert get_party(db_connection, right.id).merged_into_id is None

    pending = list_pending_match_proposals(db_connection)
    assert any(item.id == proposal.id for item in pending)

    survivor = confirm_match_proposal(
        db_connection,
        proposal.id,
        confirmed_by="tester",
        survivor_id=left.id,
        merged_id=right.id,
    )
    assert survivor.id == left.id
    assert get_party(db_connection, right.id).merged_into_id == left.id
    assert list_pending_match_proposals(db_connection) == []


def test_proposal_reject_does_not_merge(db_connection) -> None:
    left = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Delta Works A"),
    )
    right = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Delta Works B"),
    )
    candidate = MatchCandidate(
        left_id=left.id,
        right_id=right.id,
        score=0.9,
        reason="probabilistic:similarity",
        rule="probabilistic",
    )
    proposal = create_match_proposal(db_connection, candidate)
    rejected = reject_match_proposal(db_connection, proposal.id, rejected_by="tester")
    assert rejected.status == "rejected"
    assert get_party(db_connection, right.id).merged_into_id is None


def test_pending_pair_unique(db_connection) -> None:
    left = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Epsilon One"),
    )
    right = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Epsilon Two"),
    )
    candidate = MatchCandidate(
        left_id=left.id,
        right_id=right.id,
        score=0.9,
        reason="probabilistic:similarity",
        rule="probabilistic",
    )
    create_match_proposal(db_connection, candidate)
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            create_match_proposal(db_connection, candidate)


def test_confirm_wrong_ids_raises(db_connection) -> None:
    left = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Zeta Left"),
    )
    right = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Zeta Right"),
    )
    other = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Zeta Other"),
    )
    candidate = MatchCandidate(
        left_id=left.id,
        right_id=right.id,
        score=0.91,
        reason="probabilistic:similarity",
        rule="probabilistic",
    )
    proposal = create_match_proposal(db_connection, candidate)
    with pytest.raises(ProposalStateError):
        confirm_match_proposal(
            db_connection,
            proposal.id,
            confirmed_by="tester",
            survivor_id=left.id,
            merged_id=other.id,
        )


def test_proposals_table_exists(db_connection) -> None:
    exists = db_connection.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'party_match_proposals'
            """
        )
    ).scalar()
    assert exists == 1
