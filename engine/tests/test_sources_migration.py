import pytest

from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import create_source


def test_sources_unique_url_format(db_connection) -> None:
    data = SourceCreate(
        name="NOCOPO",
        jurisdiction="federal",
        category="procurement",
        url="https://nocopo.bpp.gov.ng/",
        fetch_method="http",
        format="html",
    )
    create_source(db_connection, data)
    with pytest.raises(ValueError, match="already exists"):
        create_source(db_connection, data.model_copy(update={"name": "duplicate"}))


def test_sources_defaults(db_connection) -> None:
    created = create_source(
        db_connection,
        SourceCreate(
            name="Open Treasury",
            jurisdiction="federal",
            category="payments",
            url="https://payment.gov.ng/",
            fetch_method="http",
            format="html",
        ),
    )
    assert created.status == "proposed"
    assert float(created.reliability_score) == 0.0
    assert created.health_status == "unknown"
