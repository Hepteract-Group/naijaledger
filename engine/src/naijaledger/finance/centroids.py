"""Approximate ADM1 centroids for map API (illustrative, not survey-grade).

SSO: `naijaledger/data/nigeria_states.json` (also imported by the web map).
"""

from __future__ import annotations

from naijaledger.geo_data import build_state_centroids

# code → (name, lat, lng)
STATE_CENTROIDS: dict[str, tuple[str, float, float]] = build_state_centroids()
