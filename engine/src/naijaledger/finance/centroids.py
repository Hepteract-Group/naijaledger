"""Approximate ADM1 centroids for map API (illustrative, not survey-grade).

Coordinates aligned with web/src/map/fixtures.ts.
"""

from __future__ import annotations

# code → (name, lat, lng)
STATE_CENTROIDS: dict[str, tuple[str, float, float]] = {
    "AB": ("Abia", 5.4527, 7.5248),
    "AD": ("Adamawa", 9.3265, 12.3984),
    "AK": ("Akwa Ibom", 5.0077, 7.8537),
    "AN": ("Anambra", 6.2209, 7.067),
    "BA": ("Bauchi", 10.3158, 9.8442),
    "BY": ("Bayelsa", 4.7719, 6.0699),
    "BE": ("Benue", 7.3369, 8.7404),
    "BO": ("Borno", 11.8333, 13.15),
    "CR": ("Cross River", 5.8702, 8.5988),
    "DE": ("Delta", 5.704, 5.9339),
    "EB": ("Ebonyi", 6.2649, 8.0137),
    "ED": ("Edo", 6.634, 5.93),
    "EK": ("Ekiti", 7.719, 5.311),
    "EN": ("Enugu", 6.4584, 7.5464),
    "FC": ("FCT", 9.0765, 7.3986),
    "GO": ("Gombe", 10.2897, 11.171),
    "IM": ("Imo", 5.572, 7.0588),
    "JI": ("Jigawa", 12.228, 9.5616),
    "KD": ("Kaduna", 10.5105, 7.4165),
    "KN": ("Kano", 12.0022, 8.592),
    "KT": ("Katsina", 12.9908, 7.601),
    "KE": ("Kebbi", 11.4942, 4.2333),
    "KO": ("Kogi", 7.7337, 6.6906),
    "KW": ("Kwara", 8.9669, 4.3874),
    "LA": ("Lagos", 6.5244, 3.3792),
    "NA": ("Nasarawa", 8.4991, 8.5),
    "NI": ("Niger", 9.9306, 5.5983),
    "OG": ("Ogun", 6.998, 3.4737),
    "ON": ("Ondo", 7.1, 5.05),
    "OS": ("Osun", 7.5629, 4.52),
    "OY": ("Oyo", 8.1574, 3.6147),
    "PL": ("Plateau", 9.2182, 9.5179),
    "RI": ("Rivers", 4.8156, 7.0498),
    "SO": ("Sokoto", 13.0059, 5.2476),
    "TA": ("Taraba", 8.0, 10.5),
    "YO": ("Yobe", 12.0, 11.5),
    "ZA": ("Zamfara", 12.17, 6.66),
}
