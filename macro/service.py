###############################
# macro/service.py
###############################
from typing import List, Dict, Any
import datetime as dt
import time

import yfinance as yf

from news.router import fetch_raw_news


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


# ------------------------------------------------------------------
# PERFORMANCE HEBDO
# ------------------------------------------------------------------

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
            "war",
            "conflict",
            "tension",
            "sanction",
            "gaza",
            "ukraine",
            "geopolit",
        ]
    ):
        return "geopolitics"

    if any(
        k in title
        for k in [
            "ai",
            "artificial intelligence",
            "semiconductor",
            "chip",
            "nvidia",
            "apple",
            "tesla",
            "microsoft",
            "google",
            "amazon",
            "meta",
        ]
    ):
        return "tech"

    return "companies"


def _score_title(title: str) -> float | None:
    t = title.lower()

    positives = [
        "rally",
        "surge",
        "jumps",
        "beats",
        "strong",
        "optimism",
        "gain",
        "soars",
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

    if any(w in t for w in positives):
        score += 1
        hit = True
    if any(w in t for w in negatives):
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

        date_str = d.isoformat()
        bucket = _infer_bucket(art)

        day = daily.setdefault(date_str, {})
        cell = day.setdefault(bucket, {"sum": 0.0, "scored": 0, "count": 0})

        score = _score_title(title)
        if score is not None:
            cell["sum"] += score
            cell["scored"] += 1

        cell["count"] += 1

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
# PUBLIC API (appelée par le router)
# ------------------------------------------------------------------

def build_week_raw(start: dt.date, end: dt.date) -> Dict[str, Any]:
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "created_at": time.time(),
        "asset_performances": _build_asset_performances(start, end),
        "sentiment_grid": _build_sentiment_grid(start, end),
    }
