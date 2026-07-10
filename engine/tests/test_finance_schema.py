import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from naijaledger.finance.models import PartyCreate
from naijaledger.finance.service import create_party, get_party


def test_finance_tables_exist(db_connection) -> None:
    rows = db_connection.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(:names)
            """
        ),
        {
            "names": [
                "parties",
                "party_relationships",
                "tenders",
                "awards",
                "contracts",
                "payments",
                "budget_lines",
            ]
        },
    ).all()
    assert {row[0] for row in rows} == {
        "parties",
        "party_relationships",
        "tenders",
        "awards",
        "contracts",
        "payments",
        "budget_lines",
    }


def test_create_and_get_party(db_connection) -> None:
    party = create_party(
        db_connection,
        PartyCreate(
            party_type="agency",
            canonical_name="Bureau of Public Procurement",
            identifiers={"short": "BPP"},
        ),
    )
    loaded = get_party(db_connection, party.id)
    assert loaded.canonical_name == "Bureau of Public Procurement"
    assert loaded.party_type == "agency"
    assert loaded.identifiers["short"] == "BPP"


def test_party_unique_type_name(db_connection) -> None:
    create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Acme Ltd"),
    )
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            create_party(
                db_connection,
                PartyCreate(party_type="company", canonical_name="acme ltd"),
            )


def test_tender_requires_agency_fk(db_connection) -> None:
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO tenders (agency_id, title)
                    VALUES ('00000000-0000-0000-0000-000000000001', 'Ghost tender')
                    """
                )
            )


def test_payment_source_ref_unique(db_connection) -> None:
    agency = create_party(
        db_connection,
        PartyCreate(party_type="agency", canonical_name="Open Treasury Agency"),
    )
    db_connection.execute(
        text(
            """
            INSERT INTO payments (agency_id, amount, source_ref)
            VALUES (:agency_id, 1000, 'ot-row-1')
            """
        ),
        {"agency_id": agency.id},
    )
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO payments (agency_id, amount, source_ref)
                    VALUES (:agency_id, 2000, 'ot-row-1')
                    """
                ),
                {"agency_id": agency.id},
            )


def test_tender_ocid_unique(db_connection) -> None:
    agency = create_party(
        db_connection,
        PartyCreate(party_type="agency", canonical_name="NOCOPO Agency"),
    )
    db_connection.execute(
        text(
            """
            INSERT INTO tenders (ocid, agency_id, title)
            VALUES ('ocds-x-1', :agency_id, 'Tender A')
            """
        ),
        {"agency_id": agency.id},
    )
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO tenders (ocid, agency_id, title)
                    VALUES ('ocds-x-1', :agency_id, 'Tender B')
                    """
                ),
                {"agency_id": agency.id},
            )
