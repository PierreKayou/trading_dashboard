# news/service.py

import time
from typing import Dict, List

# ------------------------------------------------------------------
# SOURCES UTILISÉES (gratuites / ouvertes)
# ------------------------------------------------------------------

NEWS_SOURCES = [
    "yfinance",
    "reuters_rss",
    "marketwatch_rss",
    "fed_statements",
    "ecb_statements",
    "crypto_news",
]

# ------------------------------------------------------------------
# RÈGLES DE PONDÉRATION (V1 → évolutif)
# ------------------------------------------------------------------

BASE_DRIVERS = {
    "macro_us": 0.0,
    "macro_eu": 0.0,
    "geopolitics": 0.0,
    "crypto": 0.0,
    "commodities": 0.0,
}

ASSET_EXPOSURE = {
    "ES": "macro_us",
    "NQ": "macro_us",
    "GC": "geopolitics",
    "CL": "geopolitics",
    "BTC": "crypto",
}

# ------------------------------------------------------------------
# MOCK NEWS SCORE (TEMPORAIRE MAIS HONNÊTE)
# -> sera remplacé par agrégation réelle (RSS / APIs)
# ------------------------------------------------------------------

def fetch_news_signals() -> Dict[str, float]:
    """
    Simule des signaux de stress par pilier macro.
    Valeurs entre 0 et 1.
    """
    return {
        "macro_us": 0.65,
        "macro_eu": 0.45,
        "geopolitics": 0.30,
        "crypto": 0.25,
        "commodities": 0.40,
    }

# ------------------------------------------------------------------
# SCORING PRINCIPAL
# ------------------------------------------------------------------

def compute_stress_score(drivers: Dict[str, float]) -> int:
    """
    Score global 0 → 100
    """
    raw = sum(drivers.values()) / max(len(drivers), 1)
    score = int(raw * 100)
    return min(max(score, 0), 100)


def risk_label_from_score(score: int) -> str:
    if score >= 70:
        return "high_risk"
    if score >= 40:
        return "neutral"
    return "low_risk"


def volatility_from_score(score: int) -> str:
    if score >= 70:
        return "high"
    if score <= 30:
        return "low"
    return "normal"


def build_asset_view(drivers: Dict[str, float]) -> Dict[str, Dict]:
    out = {}
    for asset, driver in ASSET_EXPOSURE.items():
        val = drivers.get(driver, 0)

        if val >= 0.6:
            sensitivity = "high"
            comment = f"{asset} très sensible au stress {driver.replace('_', ' ')}."
        elif val >= 0.35:
            sensitivity = "medium"
            comment = f"{asset} modérément exposé au contexte {driver.replace('_', ' ')}."
        else:
            sensitivity = "low"
            comment = f"{asset} peu affecté par le contexte actuel."

        out[asset] = {
            "sensitivity": sensitivity,
            "comment": comment,
        }
    return out


# ------------------------------------------------------------------
# API SERVICE PRINCIPAL
# ------------------------------------------------------------------

def build_stress_report() -> Dict:
    drivers = fetch_news_signals()
    score = compute_stress_score(drivers)

    return {
        "stress_score": score,
        "risk_label": risk_label_from_score(score),
        "volatility_regime": volatility_from_score(score),
        "drivers": drivers,
        "by_asset": build_asset_view(drivers),
        "created_at": time.time(),
        "sources_used": NEWS_SOURCES,
    }
