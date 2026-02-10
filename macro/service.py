###############################
# macro/service.py
###############################
from typing import List, Dict, Any
import datetime as dt
import time

import yfinance as yf

from news.service import fetch_raw_news


# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

ASSETS = {
    "ES": {"name": "S&P 500 Future", "yf": "ES=F"},
    "NQ": {"name": "Nasdaq 100 Future", "yf": "NQ=F"},
    "BTC": {"name": "Bitcoin", "yf": "BTC-USD"},
    "CL": {"name": "Crude Oil (WTI)", "yf": "CL=F"},
    "GC": {"name": "Gold", "yf": "GC=F"},
}

BUCKETS = ["macro_us", "macro_europe", "companies", "geopolitics", "tech"]


def _build_asset_performances(start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
    out = []

    for sym, cfg in ASSETS.items():
        try:
            ticker = yf.Ticker(cfg["yf"])
            hist = ticker.history(
                start=start.isoformat(),
                end=(end + dt.timedelta(days=1)).isoformat(),
                interval="1d",
            )

            if hist.empty or len(hist) < 2:
                ret = 0.0
            else:
                first = float(hist["Close"].iloc[0])
                last = float(hist["Close"].iloc[-1])
                ret = (last - first) / first * 100 if first else 0.0

        except Exception:
            ret = 0.0

        out.append(
            {
                "symbol": sym,
                "name": cfg["name"],
                "return_pct": ret,
            }
        )

    return out


# ------------------------------------------------------------------
# SENTIMENT – HELPERS
# ------------------------------------------------------------------

def _infer_bucket(article: Dict[str, Any]) -> str:
    title = (article.get("title") or "").lower()
    sym = (article.get("symbol") or "").lower()

    if sym in ["^gspc", "^ndx", "es", "nq"]:
        return "macro_us"

    if any(k in title for k in ["europe", "eurozone", "zone euro", "ecb", "bce"]):
        return "macro_europe"

    if any(
        k in title
        for k in [
            "earnings",
            "guidance",
            "quarter",
            "profit",
            "revenue",
            "results",
        ]
    ):
        return "companies"

    if any(
        k in title
        for k in [
            "war",
            "geopolitics",
            "tensions",
            "taiwan",
            "ukraine",
            "middle east",
        ]
    ):
        return "geopolitics"

    if any(k in title for k in ["ai", "chip", "semiconductor", "cloud", "saas"]):
        return "tech"

    return "macro_us"


def _score_title(title: str) -> float | None:
    """
    Score très simple :
    +1 pour mot positif, -1 pour mot négatif
    Retourne None si rien de significatif.
    """
    positives = [
        "beats",
        "beat",
        "rally",
        "soars",
        "soar",
        "jumps",
        "jump",
        "surge",
        "strong",
        "improves",
        "improvement",
    ]
    negatives = [
        "falls",
        "fall",
        "drop",
        "plunge",
        "misses",
        "weak",
        "fear",
        "selloff",
        "losses",
    ]

    score = 0
    hit = False

    low = title.lower()
    for w in positives:
        if w in low:
            score += 1
            hit = True

    for w in negatives:
        if w in low:
            score -= 1
            hit = True

    return score if hit else None


# ------------------------------------------------------------------
# SENTIMENT GRID
# ------------------------------------------------------------------

def _build_sentiment_grid(start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
    try:
        raw = fetch_raw_news(max_articles=400)
    except Exception:
        raw = {"articles": []}

    articles = raw.get("articles", []) or []

    # daily[date][bucket] = {sum, scored, count}
    daily: Dict[str, Dict[str, Dict[str, float]]] = {}

    for art in articles:
        title = (art.get("title") or "").strip()
        if not title:
            continue

        ts = art.get("providerPublishTime")
        if not ts:
            continue

        # correction ms → s
        if ts > 10_000_000_000:
            ts = ts / 1000

        try:
            d = dt.datetime.utcfromtimestamp(ts).date()
        except Exception:
            continue

        if d < start or d > end:
            continue

        bucket = _infer_bucket(art)
        score = _score_title(title)
        date_key = d.isoformat()

        if date_key not in daily:
            daily[date_key] = {}

        if bucket not in daily[date_key]:
            daily[date_key][bucket] = {"sum": 0.0, "scored": 0.0, "count": 0.0}

        daily[date_key][bucket]["count"] += 1
        if score is not None:
            daily[date_key][bucket]["sum"] += score
            daily[date_key][bucket]["scored"] += 1

    grid: List[Dict[str, Any]] = []
    cur = start
    while cur <= end:
        date_str = cur.isoformat()
        day = daily.get(date_str, {})

        for bucket in BUCKETS:
            info = day.get(bucket)
            if not info:
                grid.append(
                    {
                        "date": date_str,
                        "bucket": bucket,
                        "sentiment": 0.0,
                        "news_count": 0,
                    }
                )
            else:
                if info["scored"] > 0:
                    avg = info["sum"] / info["scored"]
                else:
                    avg = None

                grid.append(
                    {
                        "date": date_str,
                        "bucket": bucket,
                        "sentiment": avg,
                        "news_count": info["count"],
                    }
                )

        cur += dt.timedelta(days=1)

    return grid


# ------------------------------------------------------------------
# PUBLIC API : RAW (pour /api/macro/week/raw)
# ------------------------------------------------------------------

def build_week_raw(start: dt.date, end: dt.date) -> Dict[str, Any]:
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "created_at": time.time(),
        "asset_performances": _build_asset_performances(start, end),
        "sentiment_grid": _build_sentiment_grid(start, end),
    }


# ------------------------------------------------------------------
# PUBLIC API : SUMMARY HEBDO (pour /api/macro/week/summary)
# ------------------------------------------------------------------

def build_week_summary(start: dt.date, end: dt.date) -> Dict[str, Any]:
    """
    Construit un résumé hebdo simple à partir des perfs d'actifs.
    - risk_on : True / False / None
    - risk_comment : texte FR
    - top_moves : top 3 mouvements (en %)
    """
    raw = build_week_raw(start, end)
    assets = raw.get("asset_performances", []) or []

    # On regarde surtout ES + NQ pour le biais global
    es = next((a for a in assets if a.get("symbol") == "ES"), None)
    nq = next((a for a in assets if a.get("symbol") == "NQ"), None)

    risk_on: bool | None = None
    if es and nq:
        avg = (es.get("return_pct", 0.0) + nq.get("return_pct", 0.0)) / 2
        if avg > 0.5:
            risk_on = True
        elif avg < -0.5:
            risk_on = False

    if risk_on is True:
        risk_comment = (
            "Biais global plutôt risk-on cette semaine sur les indices US."
        )
    elif risk_on is False:
        risk_comment = (
            "Biais global plutôt risk-off cette semaine sur les indices US."
        )
    else:
        risk_comment = (
            "Biais global neutre ou mitigé cette semaine sur les indices US."
        )

    # Top 3 mouvements absolus
    moves: List[Dict[str, Any]] = []
    sorted_assets = sorted(
        assets, key=lambda a: abs(a.get("return_pct", 0.0)), reverse=True
    )

    for a in sorted_assets[:3]:
        ret = float(a.get("return_pct", 0.0))
        moves.append(
            {
                "description": f"Mouvement de {ret:+.2f}% sur {a.get('name', a.get('symbol'))}",
                "asset": a.get("symbol"),
                "move_pct": ret,
                "event_id": None,
            }
        )

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "risk_on": risk_on,
        "risk_comment": risk_comment,
        "top_events": [],       # à enrichir plus tard avec le calendrier éco
        "top_moves": moves,
        "upcoming_focus": [],   # placeholders pour la suite
    }


# ------------------------------------------------------------------
# CACHE DÉDIÉ POUR LE RÉSUMÉ HEBDO
# ------------------------------------------------------------------

_SUMMARY_CACHE_DATA: Dict[str, Any] | None = None
_SUMMARY_CACHE_KEY: tuple[dt.date, dt.date] | None = None
_SUMMARY_CACHE_TS: float = 0.0
_SUMMARY_CACHE_TTL_SECONDS = 300  # 5 minutes


def get_week_summary_cached(
    start: dt.date,
    end: dt.date,
    ttl_seconds: int = _SUMMARY_CACHE_TTL_SECONDS,
) -> Dict[str, Any]:
    """
    Version mise en cache de build_week_summary pour éviter
    de frapper yfinance et les news externes à chaque appel.
    """
    global _SUMMARY_CACHE_DATA, _SUMMARY_CACHE_KEY, _SUMMARY_CACHE_TS

    now = time.time()
    key = (start, end)

    if (
        _SUMMARY_CACHE_DATA is not None
        and _SUMMARY_CACHE_KEY == key
        and now - _SUMMARY_CACHE_TS < ttl_seconds
    ):
        return _SUMMARY_CACHE_DATA

    summary = build_week_summary(start, end)
    _SUMMARY_CACHE_DATA = summary
    _SUMMARY_CACHE_KEY = key
    _SUMMARY_CACHE_TS = now
    return summary
