"""Unit tests for graph read helpers and public subgraph API."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from naijaledger.api.app import create_app
from naijaledger.api.v1.graph import get_memgraph_client
from naijaledger.graph.read import (
    clamp_subgraph_limit,
    display_name_for_node,
    fetch_subgraph,
    kind_for_labels,
    unavailable_subgraph,
)


def test_kind_and_display_name() -> None:
    assert kind_for_labels(["Agency", "FinanceParty"]) == "party"
    assert kind_for_labels(["Tender"]) == "tender"
    assert kind_for_labels(["Award"]) == "award"
    assert kind_for_labels(["Contract"]) == "contract"
    assert kind_for_labels(["Other"]) is None
    assert display_name_for_node(["Tender"], {"id": "abc", "title": "Road"}) == "Road"
    assert display_name_for_node(["Award"], {"id": "abcdef12-xxxx"}) == "Award · abcdef12"


def test_clamp_subgraph_limit() -> None:
    assert clamp_subgraph_limit(None) == 80
    assert clamp_subgraph_limit(0) == 1
    assert clamp_subgraph_limit(999) == 200


class _FakeNode:
    def __init__(self, labels: list[str], props: dict[str, Any]) -> None:
        self.labels = labels
        self._props = props

    def __iter__(self):
        return iter(self._props.items())

    def keys(self):
        return self._props.keys()

    def __getitem__(self, key: str) -> Any:
        return self._props[key]


def test_fetch_subgraph_sample_with_fake_driver() -> None:
    agency = _FakeNode(["Agency", "FinanceParty"], {"id": "a1", "name": "Works"})
    tender = _FakeNode(["Tender"], {"id": "t1", "title": "Road works", "ocid": "ocds-1"})
    session = MagicMock()
    session.run.side_effect = [
        [{"n": agency}, {"n": tender}],
        [
            {
                "source": "a1",
                "target": "t1",
                "rel_type": "ISSUED",
                "rid": 1,
            }
        ],
    ]
    session.__enter__ = lambda s: s
    session.__exit__ = MagicMock(return_value=False)
    driver = MagicMock()
    driver.session.return_value = session

    doc = fetch_subgraph(driver, limit=10)
    assert doc["available"] is True
    assert doc["demo"] is False
    assert {n["id"] for n in doc["nodes"]} == {"a1", "t1"}
    assert doc["nodes"][0]["kind"] in {"party", "tender"}
    assert len(doc["links"]) == 1
    assert doc["links"][0]["rel_type"] == "ISSUED"


def test_fetch_subgraph_ego_seed_with_fake_driver() -> None:
    agency = _FakeNode(["Agency", "FinanceParty"], {"id": "a1", "name": "Works"})
    tender = _FakeNode(["Tender"], {"id": "t1", "title": "Road works"})
    session = MagicMock()
    session.run.side_effect = [
        [
            {
                "seed": agency,
                "r": object(),
                "m": tender,
                "start_n": agency,
                "end_n": tender,
                "rel_type": "ISSUED",
                "rid": 7,
            }
        ],
    ]
    session.__enter__ = lambda s: s
    session.__exit__ = MagicMock(return_value=False)
    driver = MagicMock()
    driver.session.return_value = session

    doc = fetch_subgraph(driver, seed_id="a1", limit=10)
    assert doc["id"] == "live-a1"
    assert {n["id"] for n in doc["nodes"]} == {"a1", "t1"}
    by_id = {n["id"]: n for n in doc["nodes"]}
    assert by_id["a1"]["kind"] == "party"
    assert by_id["t1"]["kind"] == "tender"
    assert by_id["t1"]["name"] == "Road works"
    assert len(doc["links"]) == 1
    assert doc["links"][0]["source"] == "a1"
    assert doc["links"][0]["target"] == "t1"
    assert doc["links"][0]["rel_type"] == "ISSUED"


def test_unavailable_subgraph_shape() -> None:
    doc = unavailable_subgraph()
    assert doc["available"] is False
    assert doc["nodes"] == []
    assert doc["links"] == []


@pytest.fixture
def graph_api_client() -> Generator[TestClient, None, None]:
    application = create_app()

    def _none() -> Generator[None, None, None]:
        yield None

    application.dependency_overrides[get_memgraph_client] = _none
    client = TestClient(application)
    yield client
    application.dependency_overrides.clear()


def test_graph_subgraph_unavailable(graph_api_client: TestClient) -> None:
    response = graph_api_client.get("/v1/graph/subgraph")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["demo"] is False
    assert body["nodes"] == []
    assert body["links"] == []


def test_graph_subgraph_live_override() -> None:
    application = create_app()
    agency = _FakeNode(["Agency", "FinanceParty"], {"id": "a1", "name": "Works"})
    session = MagicMock()
    session.run.side_effect = [
        [{"n": agency}],
        [],
    ]
    session.__enter__ = lambda s: s
    session.__exit__ = MagicMock(return_value=False)
    driver = MagicMock()
    driver.session.return_value = session
    fake_client = MagicMock()
    fake_client._driver = driver
    fake_client.driver = driver
    fake_client.close = MagicMock()

    def _client() -> Generator[Any, None, None]:
        yield fake_client

    application.dependency_overrides[get_memgraph_client] = _client
    client = TestClient(application)
    try:
        response = client.get("/v1/graph/subgraph", params={"limit": 10})
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["nodes"][0]["name"] == "Works"
        assert body["nodes"][0]["kind"] == "party"
    finally:
        application.dependency_overrides.clear()
