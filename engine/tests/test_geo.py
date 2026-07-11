"""Unit tests for geo helpers and facet URL parsing companions."""

from naijaledger.finance.geo import (
    normalize_lga,
    normalize_state_code,
    parse_fiscal_year,
)


def test_normalize_state_code() -> None:
    assert normalize_state_code("EK") == "EK"
    assert normalize_state_code("ekiti") == "EK"
    assert normalize_state_code("Ekiti State") == "EK"
    assert normalize_state_code("Lagos") == "LA"
    assert normalize_state_code("") is None
    assert normalize_state_code("Narnia") is None


def test_normalize_lga_drops_state_labels() -> None:
    assert normalize_lga("ADO-EKITI") == "ADO-EKITI"
    assert normalize_lga("EKITI- STATE") is None
    assert normalize_lga("  ") is None


def test_parse_fiscal_year() -> None:
    assert parse_fiscal_year("2026") == 2026
    assert parse_fiscal_year("26") is None
    assert parse_fiscal_year("") is None
