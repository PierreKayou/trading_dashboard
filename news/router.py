# news/router.py — V2
# ---------------------------------------------
# Agrégation + normalisation des news macro
# Usage : prop firm / trading discrétionnaire
# ---------------------------------------------

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import time
import hashlib
import datetime as dt
import requests

router = APIRouter(prefix="/api/news", tags=["news"])

# =====================================================
# CONFIG SOURCES GRATUITES
# =====================================================

REUTERS_RSS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.reuters.com/reuters/marketsNews",
]

YF_NEWS_URL = "https://query1.finance.yahoo.com/v1/finance/news"

HEADERS = {
    "User-Agent": "StarkMacroBot/1.0"
}

# =====================================================
# TAXONOMIE OFFICIELLE
# =====================================================

CATEGORIES = {
    "monetary_policy": ["fed", "fomc", "ecb", "rates", "interest", "qt"],
    "inflation": ["cpi", "inflation", "pce", "prices"],
    "growth": ["gdp", "growth", "pmi", "ism", "recession"],
    "employment": ["jobs", "employment", "nfp", "unemployment", "wages"],
    "geopolitics": ["war", "conflict", "sanction", "geopolit"],
    "tech": ["ai", "chip", "semiconductor", "nvidia", "apple", "microsoft"],
    "commodities": ["oil", "gold", "energy", "supply"],
    "crypto": ["bitcoin", "crypto", "etf", "regulation"],
    "risk_event": ["crisis", "stress", "collapse", "default"],
}

ASSET_HINTS = {
    "ES": ["fed", "rates", "inflation", "gdp"],
    "NQ": ["tech", "ai", "semiconductor"],
    "BTC": ["bitcoin", "crypto", "etf", "regulation"],
    "CL": ["oil", "energy", "opec", "supply"],
    "GC": ["gold", "inflation", "risk", "crisis"],
}

# =====================================================
# MODELS
# =====================================================

class NormalizedNews(BaseModel):
    id: str
    timestamp: int
    source: str
    category: str
    importance: str
    headline: str
    summary: Optional[str]
    assets_hint: List[str]
    sentiment_hint: Optional[str]
    time_horizon: str


# =====================================================
# HELPERS
# =====================================================

def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _detect_category(text: str) -> str:
    t = text.lower()
    for cat, keys in CATEGORIES.items():
        if any(k in t for k in keys):
            return cat
    return "growth"


def _detect_assets(text: str) -> List[str]:
    t = text.lower()
    assets = []
    for asset, keys in ASSET_HINTS.items():
        if any(k in t for k in keys):
            assets.append(asset)
    return assets or ["ES"]


def _importance_from_text(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["fed", "rates", "cpi", "war", "crisis"]):
        return "high"
    if any(k in t for k in ["earnings", "growth", "jobs"]):
        return "medium"
    return "low"


def _sentiment_from_text(text: str) -> Optional[str]:
    t = text.lower()
    if any(k in t for k in ["fall", "drop", "risk", "stress", "concern"]):
        return "negative"
    if any(k in t for k in ["rise", "strong", "optimism", "growth"]):
        return "positive"
    return None


# =====================================================
# FETCHERS
# =====================================================

def fetch_reuters() -> List[Dict]:
    items = []
    for feed in REUTERS_RSS:
        try:
            resp = requests.get(feed, timeout=6)
            if resp.ok:
                items.append(resp.text)
        except Exception:
            continue
    return items


def fetch_yahoo_finance(limit: int = 20) -> List[Dict]:
    try:
        resp = requests.get(
            YF_NEWS_URL,
            params={"category": "general", "count": limit},
            headers=HEADERS,
            timeout=6,
        )
        if not resp.ok:
            return []
        return resp.json().get("items", [])
    except Exception:
        return []


# =====================================================
# NORMALIZATION
# =====================================================

def normalize_news(raw: Dict, source: str) -> NormalizedNews:
    headline = raw.get("title") or raw.get("headline") or "Untitled"
    summary = raw.get("summary") or raw.get("description")

    ts = raw.get("pubDate") or raw.get("published_at")
    timestamp = int(time.time()) if not ts else int(time.time())

    category = _detect_category(headline)
    importance = _importance_from_text(headline)
    assets = _detect_assets(headline)
    sentiment = _sentiment_from_text(headline)

    return NormalizedNews(
        id=_hash(headline + source),
        timestamp=timestamp,
        source=source,
        category=category,
        importance=importance,
        headline=headline,
        summary=summary,
        assets_hint=assets,
        sentiment_hint=sentiment,
        time_horizon="intraday" if importance == "high" else "short_term",
    )


# =====================================================
# PUBLIC ENDPOINT
# =====================================================

@router.get("/normalized", response_model=List[NormalizedNews])
def get_normalized_news(limit: int = 25):
    """
    Endpoint principal NEWS V2
    Renvoie un flux normalisé prêt pour l'IA.
    """
    normalized: List[NormalizedNews] = []
    seen = set()

    # Yahoo Finance
    yf_items = fetch_yahoo_finance(limit=limit)
    for it in yf_items:
        n = normalize_news(it, "yahoo_finance")
        if n.id not in seen:
            seen.add(n.id)
            normalized.append(n)

    # Hard cap
    normalized = sorted(
        normalized,
        key=lambda x: (x.importance, x.timestamp),
        reverse=True,
    )[:limit]

    return normalized
