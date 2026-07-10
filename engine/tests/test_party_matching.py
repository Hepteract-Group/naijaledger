import pytest

from naijaledger.finance.matching import normalize_party_name, score_party_pair
from naijaledger.finance.models import PartyCreate
from naijaledger.finance.service import (
    PartyMergeError,
    apply_party_merge,
    canonical_party_id,
    create_party,
    propose_party_matches,
)


def test_normalize_party_name_strips_suffixes() -> None:
    assert normalize_party_name("A.B.C. Limited") == normalize_party_name("abc ltd")
    assert normalize_party_name("Acme Nig. Ltd") == "acme"


def test_deterministic_shared_rc(db_connection) -> None:
    left = create_party(
        db_connection,
        PartyCreate(
            party_type="company",
            canonical_name="Alpha Construction XYZ",
            identifiers={"rc": "RC-100"},
        ),
    )
    right = create_party(
        db_connection,
        PartyCreate(
            party_type="company",
            canonical_name="Completely Different Name Ltd",
            identifiers={"rc": "RC-100"},
        ),
    )
    match = score_party_pair(left, right)
    assert match is not None
    assert match.rule == "deterministic"
    assert match.score == 1.0
    assert "identifier" in match.reason


def test_probabilistic_near_duplicate(db_connection) -> None:
    left = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Zenith Building Services"),
    )
    right = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Zenith Building Service"),
    )
    match = score_party_pair(left, right)
    assert match is not None
    assert match.rule == "probabilistic"
    assert match.score >= 0.82


def test_propose_and_merge(db_connection) -> None:
    survivor = create_party(
        db_connection,
        PartyCreate(
            party_type="company",
            canonical_name="Beta Supplies Ltd",
            identifiers={"tin": "TIN-9"},
        ),
    )
    duplicate = create_party(
        db_connection,
        PartyCreate(
            party_type="company",
            canonical_name="Beta Supplies Limited",
            identifiers={"tin": "TIN-9"},
        ),
    )
    create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Unrelated Vendor Plc"),
    )

    proposals = propose_party_matches(db_connection, survivor.id)
    assert any(item.right_id == duplicate.id for item in proposals)

    updated = apply_party_merge(
        db_connection,
        survivor_id=survivor.id,
        merged_id=duplicate.id,
    )
    assert "Beta Supplies Limited" in updated.aliases
    assert updated.identifiers["tin"] == "TIN-9"
    assert canonical_party_id(db_connection, duplicate.id) == survivor.id

    with pytest.raises(PartyMergeError):
        apply_party_merge(
            db_connection,
            survivor_id=survivor.id,
            merged_id=duplicate.id,
        )
