"""Load Nigeria ADM1 codes, names, aliases, and map centroids from package JSON."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import TypedDict


class StateEntry(TypedDict):
    code: str
    name: str
    lat: float
    lng: float
    aliases: list[str]


@lru_cache(maxsize=1)
def load_nigeria_states() -> tuple[StateEntry, ...]:
    raw = resources.files("naijaledger.geo").joinpath("nigeria_states.json").read_text(
        encoding="utf-8"
    )
    rows = json.loads(raw)
    return tuple(
        StateEntry(
            code=row["code"],
            name=row["name"],
            lat=float(row["lat"]),
            lng=float(row["lng"]),
            aliases=list(row.get("aliases") or []),
        )
        for row in rows
    )


def build_state_code_to_name() -> dict[str, str]:
    return {row["code"]: row["name"] for row in load_nigeria_states()}


def build_state_name_to_code() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in load_nigeria_states():
        mapping[row["name"].lower()] = row["code"]
        for alias in row["aliases"]:
            mapping[alias.lower()] = row["code"]
    return mapping


def build_state_centroids() -> dict[str, tuple[str, float, float]]:
    return {row["code"]: (row["name"], row["lat"], row["lng"]) for row in load_nigeria_states()}
