from fastapi import APIRouter
from datetime import datetime, date, time, timedelta
from typing import Optional, Literal
import datetime as dt
import yfinance as yf

from macro.service import build_week_raw, get_week_summary_cached

router = APIRouter(prefix="/macro")

# ==============================
# Types
# ==============================

RiskMode = Literal["risk_on", "risk_off", "neutral"]
VolatilityLevel = Literal["low", "medium", "high"]

# ==============================
# /api/macro/snapshot
# ==============================

@router.get("/snapshot")
def macro_snapshot():
    today = date.today()
    start = today - timedelta(days=7)

    summary = get_week_summary_cached(start, today)
    raw = build_week_raw(start, today)
    assets = raw.get("asset_performances", []) or []

    risk_flag = summary.get("risk_on")
    if risk_flag is True:
        risk_mode: RiskMode = "risk_on"
    elif risk_flag is False:
        risk_mode = "risk_off"
    else:
        risk_mode = "neutral"

    max_abs_move = max(
        (abs(float(a.get("return_pct", 0.0))) for a in assets),
        default=0.0
    )

    if max_abs_move < 1.0:
        volatility: VolatilityLevel = "low"
    elif max_abs_move < 3.0:
        volatility = "medium"
    else:
        volatility = "high"

    def get_ret(sym):
        for a in assets:
            if a.get("symbol") == sym:
                return float(a.get("return_pct", 0.0))
        return None

    es, nq = get_ret("ES"), get_ret("NQ")
    btc, cl, gc = get_ret("BTC"), get_ret("CL"), get_ret("GC")

    def bias(v):
        if v is None:
            return "neutral"
        if v > 0.5:
            return "bullish"
        if v < -0.5:
            return "bearish"
        return "neutral"

    equities = bias(((es or 0) + (nq or 0)) / 2 if es and nq else es or nq)
    commodities = bias(((cl or 0) + (gc or 0)) / 2 if cl and gc else cl or gc)
    crypto = bias(btc)

    comment = summary.get("risk_comment", "")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "risk_mode": risk_mode,
        "volatility": volatility,
        "bias": {
            "equities": equities,
            "rates": "neutral",
            "usd": "neutral",
            "credit": "neutral",
            "commodities": commodities,
            "crypto": crypto,
        },
        "comment": comment,
    }

# ==============================
# /api/macro/orientation
# ==============================

@router.get("/orientation")
def macro_orientation():
    today = date.today()
    start = today - timedelta(days=7)

    summary = get_week_summary_cached(start, today)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "risk": "on" if summary.get("risk_on") else "off" if summary.get("risk_on") is False else "neutral",
        "confidence": 0.65,
        "comment": summary.get("risk_comment", ""),
        "notes": [m.get("description") for m in summary.get("top_moves", [])],
    }

# ==============================
# /api/macro/indices
# ==============================

@router.get("/indices")
def macro_indices():
    today = dt.date.today()
    start = today - dt.timedelta(days=60)

    indices = {
        "SPX": ("S&P 500", "^GSPC"),
        "NDX": ("Nasdaq 100", "^NDX"),
        "CAC40": ("CAC 40", "^FCHI"),
        "DAX": ("DAX 40", "^GDAXI"),
        "BTC": ("Bitcoin", "BTC-USD"),
    }

    out = []

    for sym, (label, yf_sym) in indices.items():
        try:
            t = yf.Ticker(yf_sym)
            hist = t.history(start=start.isoformat(), end=(today + dt.timedelta(days=1)).isoformat())
            c = hist["Close"]
            def ret(p): return (c.iloc[-1] - c.iloc[-(p+1)]) / c.iloc[-(p+1)] * 100 if len(c) > p else None
            out.append({
                "symbol": sym,
                "name": label,
                "daily": ret(1),
                "weekly": ret(5),
                "monthly": ret(21),
            })
        except Exception:
            out.append({"symbol": sym, "name": label, "daily": None, "weekly": None, "monthly": None})

    return out

# ==============================
# /api/macro/calendar
# ==============================

@router.get("/calendar")
def macro_calendar(days_ahead: int = 2):
    today = date.today()
    return [
        {"date": today.isoformat(), "time": "14:30", "event": "CPI US", "impact": "high", "country": "US"},
        {"date": today.isoformat(), "time": "16:00", "event": "ISM Services", "impact": "medium", "country": "US"},
        {"date": (today + timedelta(days=1)).isoformat(), "time": "20:00", "event": "Minutes FOMC", "impact": "high", "country": "US"},
    ]

# ==============================
# /api/macro/sentiment_grid (PROXY QUI MARCHE)
# ==============================

@router.get("/sentiment_grid")
def macro_sentiment_grid():
    today = dt.date.today()
    start = today - dt.timedelta(days=10)

    bucket_map = {
        "macro_us": "^GSPC",
        "macro_europe": "^FCHI",
        "companies": "^NDX",
    }

    returns = {}

    for bucket, yf_sym in bucket_map.items():
        try:
            hist = yf.Ticker(yf_sym).history(
                start=start.isoformat(),
                end=(today + dt.timedelta(days=1)).isoformat(),
                interval="1d",
            )
            pct = hist["Close"].pct_change().dropna()
            returns[bucket] = {idx.date(): float(v) * 100 for idx, v in pct.items()}
        except Exception:
            returns[bucket] = {}

    dates = sorted({d for m in returns.values() for d in m if d <= today})[-5:]

    def score(v):
        if v is None:
            return None
        s = v / 5.0
        return max(-1.0, min(1.0, s))

    grid = []

    for d in dates:
        for bucket in ["macro_us", "macro_europe", "companies", "geopolitics", "tech"]:
            if bucket in returns:
                sentiment = score(returns[bucket].get(d))
            else:
                sentiment = None
            grid.append({
                "date": d.isoformat(),
                "bucket": bucket,
                "sentiment": sentiment,
            })

    return {
        "start": dates[0].isoformat() if dates else today.isoformat(),
        "end": dates[-1].isoformat() if dates else today.isoformat(),
        "grid": grid,
    }
