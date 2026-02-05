# news/analysis_v2.py
# -------------------------------------------------
# IA NEWS V2 — Analyse macro structurée
# Usage : prop firm / trading discrétionnaire
# -------------------------------------------------

from fastapi import APIRouter, HTTPException
from typing import Dict, List
import time
import statistics

from news.router import NormalizedNews, get_normalized_news

router = APIRouter(prefix="/api/news", tags=["news-v2"])


# =====================================================
# LOGIQUE MACRO
# =====================================================

RISK_KEYWORDS = {
    "risk_on": ["growth", "optimism", "strong", "rally"],
    "risk_off": ["risk", "stress", "crisis", "war", "tightening"],
}

VOL_KEYWORDS = {
    "high": ["crisis", "war", "collapse", "stress", "shock"],
    "low": ["stable", "contained", "calm"],
}


def infer_risk_tone(news: List[NormalizedNews]) -> str:
    score = 0
    for n in news:
        text = n.headline.lower()
        if any(k in text for k in RISK_KEYWORDS["risk_on"]):
            score += 1
        if any(k in text for k in RISK_KEYWORDS["risk_off"]):
            score -= 1

    if score >= 2:
        return "risk_on"
    if score <= -2:
        return "risk_off"
    return "neutral"


def infer_volatility(news: List[NormalizedNews]) -> str:
    for n in news:
        text = n.headline.lower()
        if any(k in text for k in VOL_KEYWORDS["high"]):
            return "high"
    return "normal"


def asset_bias(news: List[NormalizedNews], asset: str) -> Dict:
    relevant = [n for n in news if asset in n.assets_hint]
    if not relevant:
        return {"bias": "neutral", "confidence": 0.0}

    score = 0
    for n in relevant:
        if n.sentiment_hint == "positive":
            score += 1
        if n.sentiment_hint == "negative":
            score -= 1

    if score > 0:
        return {"bias": "bullish", "confidence": min(1.0, score / len(relevant))}
    if score < 0:
        return {"bias": "bearish", "confidence": min(1.0, abs(score) / len(relevant))}
    return {"bias": "neutral", "confidence": 0.3}


# =====================================================
# ENDPOINT PUBLIC
# =====================================================

@router.get("/analyze-v2")
def analyze_news_v2(limit: int = 25):
    """
    Analyse macro IA V2 basée sur news normalisées.
    """
    try:
        news = get_normalized_news(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not news:
        return {
            "status": "empty",
            "message": "Aucune news exploitable.",
            "created_at": time.time(),
        }

    risk_tone = infer_risk_tone(news)
    volatility = infer_volatility(news)

    assets = ["ES", "NQ", "BTC", "CL", "GC"]
    by_asset = {a: asset_bias(news, a) for a in assets}

    # Thèmes dominants
    categories = [n.category for n in news]
    dominant_themes = sorted(
        set(categories),
        key=lambda c: categories.count(c),
        reverse=True,
    )[:3]

    return {
        "created_at": time.time(),
        "risk_tone": risk_tone,
        "volatility": volatility,
        "dominant_themes": dominant_themes,
        "assets": by_asset,
        "news_used": len(news),
        "note": (
            "Analyse basée uniquement sur le flux de news. "
            "Aucune donnée prix ou technique n’est intégrée."
        ),
    }
