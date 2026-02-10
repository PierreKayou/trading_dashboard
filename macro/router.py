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
# Helpers indices (yfinance)
# ==============================

INDEX_SYMBOLS = {
    "SPX": {"label": "S&P 500", "yf": "^GSPC"},
    "NDX": {"label": "Nasdaq 100", "yf": "^NDX"},
    "DAX": {"label": "DAX 40", "yf": "^GDAXI"},
    "CAC40": {"label": "CAC 40", "yf": "^FCHI"},
    "EURUSD": {"label": "EUR / USD", "yf": "EURUSD=X"},
    "USDJPY": {"label": "USD / JPY", "yf": "JPY=X"},
    "BTCUSD": {"label": "Bitcoin", "yf": "BTC-USD"},
}

_INDICES_CACHE_DATA: dict | None = None
_INDICES_CACHE_TS: datetime | None = None
_INDICES_CACHE_TTL_SECONDS = 300  # 5 minutes


def _compute_return_pct(close_series, periods: int) -> Optional[float]:
    if close_series is None:
        return None

    series = close_series.dropna()
    if len(series) <= periods:
        return None

    first = float(series.iloc[-(periods + 1)])
    last = float(series.iloc[-1])
    if first == 0:
        return None

    return (last - first) / first * 100.0


# ==============================
# /api/macro/snapshot
# ==============================

@router.get("/snapshot")
def macro_snapshot():
    """
    Vue macro globale utilisée par la carte principale.
    Basée sur le résumé hebdo (ES, NQ, BTC, CL, GC + news).
    """
    today = date.today()
    start = today - timedelta(days=7)

    summary = get_week_summary_cached(start, today)
    raw = build_week_raw(start, today)
    assets = raw.get("asset_performances", []) or []

    # ---- risk mode ----
    risk_flag = summary.get("risk_on")
    if risk_flag is True:
        risk_mode: RiskMode = "risk_on"
    elif risk_flag is False:
        risk_mode = "risk_off"
    else:
        risk_mode = "neutral"

    # ---- volatilité (max move hebdo) ----
    max_abs_move = 0.0
    for a in assets:
        try:
            v = float(a.get("return_pct", 0.0) or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        max_abs_move = max(max_abs_move, abs(v))

    if max_abs_move < 1.0:
        volatility: VolatilityLevel = "low"
    elif max_abs_move < 3.0:
        volatility = "medium"
    else:
        volatility = "high"

    # ---- biais par classe d’actifs ----

    def _get_ret(symbol: str) -> Optional[float]:
        for a in assets:
            if a.get("symbol") == symbol:
                try:
                    return float(a.get("return_pct", 0.0))
                except (TypeError, ValueError):
                    return None
        return None

    es_ret = _get_ret("ES")
    nq_ret = _get_ret("NQ")
    btc_ret = _get_ret("BTC")
    cl_ret = _get_ret("CL")
    gc_ret = _get_ret("GC")

    def _classify_bias(v: Optional[float], up: float = 0.5, down: float = -0.5) -> str:
        if v is None:
            return "neutral"
        if v > up:
            return "bullish"
        if v < down:
            return "bearish"
        return "neutral"

    if es_ret is not None and nq_ret is not None:
        equities_bias = _classify_bias((es_ret + nq_ret) / 2.0)
    else:
        equities_bias = _classify_bias(es_ret or nq_ret)

    commodity_vals = [v for v in (cl_ret, gc_ret) if v is not None]
    if commodity_vals:
        commodities_bias = _classify_bias(sum(commodity_vals) / len(commodity_vals))
    else:
        commodities_bias = "neutral"

    crypto_bias = _classify_bias(btc_ret)

    bias = {
        "equities": equities_bias,
        "rates": "neutral",
        "usd": "neutral",
        "credit": "neutral",
        "commodities": commodities_bias,
        "crypto": crypto_bias,
    }

    # ---- commentaire ----
    comment = summary.get("risk_comment") or (
        "Pas assez de données récentes pour établir un biais macro clair."
    )
    top_moves = summary.get("top_moves") or []
    if top_moves:
        first = top_moves[0]
        desc = first.get("description")
        if desc:
            comment = f"{comment} {desc}"

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "risk_mode": risk_mode,
        "volatility": volatility,
        "bias": bias,
        "comment": comment,
    }


# ==============================
# /api/macro/orientation
# ==============================

@router.get("/orientation")
def macro_orientation():
    """
    Orientation de marché plus narrative pour la carte "Orientation globale".
    """
    today = date.today()
    start = today - timedelta(days=7)

    summary = get_week_summary_cached(start, today)
    raw = build_week_raw(start, today)
    assets = raw.get("asset_performances", []) or []

    risk_flag = summary.get("risk_on")
    if risk_flag is True:
        risk = "on"
    elif risk_flag is False:
        risk = "off"
    else:
        risk = "neutral"

    def _get_ret(symbol: str) -> Optional[float]:
        for a in assets:
            if a.get("symbol") == symbol:
                try:
                    return float(a.get("return_pct", 0.0))
                except (TypeError, ValueError):
                    return None
        return None

    es_ret = _get_ret("ES")
    nq_ret = _get_ret("NQ")

    avg = None
    if es_ret is not None and nq_ret is not None:
        avg = (es_ret + nq_ret) / 2.0
    elif es_ret is not None:
        avg = es_ret
    elif nq_ret is not None:
        avg = nq_ret

    confidence = 0.5
    if avg is not None:
        mag = abs(avg)
        if mag < 0.5:
            confidence = 0.4
        elif mag < 1.5:
            confidence = 0.65
        elif mag < 3.0:
            confidence = 0.8
        else:
            confidence = 0.9

    notes: list[str] = []

    risk_comment = summary.get("risk_comment")
    if risk_comment:
        notes.append(risk_comment)

    top_moves = summary.get("top_moves") or []
    if top_moves:
        desc = top_moves[0].get("description")
        if desc:
            notes.append(desc)

    upcoming = summary.get("upcoming_focus") or []
    for u in upcoming[:2]:
        if isinstance(u, str):
            notes.append(u)
        elif isinstance(u, dict):
            label = u.get("label") or u.get("description")
            if label:
                notes.append(label)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "risk": risk,
        "confidence": confidence,
        "comment": risk_comment or "",
        "notes": notes,
    }


# ==============================
# /api/macro/indices
# ==============================

@router.get("/indices")
def macro_indices():
    """
    Performance des grands indices (Jour / Semaine / Mois).
    """
    today = dt.date.today()
    start = today - dt.timedelta(days=60)

    global _INDICES_CACHE_DATA, _INDICES_CACHE_TS
    now = datetime.utcnow()

    if (
        _INDICES_CACHE_DATA is not None
        and _INDICES_CACHE_TS is not None
        and (now - _INDICES_CACHE_TS).total_seconds() < _INDICES_CACHE_TTL_SECONDS
        and _INDICES_CACHE_DATA.get("as_of") == today.isoformat()
    ):
        assets = _INDICES_CACHE_DATA.get("assets") or []
        return [
            {
                "symbol": a.get("symbol"),
                "name": a.get("label"),
                "daily": a.get("d"),
                "weekly": a.get("w"),
                "monthly": a.get("m"),
            }
            for a in assets
        ]

    assets = []
    for sym, cfg in INDEX_SYMBOLS.items():
        label = cfg["label"]
        yf_symbol = cfg["yf"]

        d_ret = w_ret = m_ret = None
        try:
            t = yf.Ticker(yf_symbol)
            hist = t.history(
                start=start.isoformat(),
                end=(today + dt.timedelta(days=1)).isoformat(),
                interval="1d",
            )
            if not hist.empty:
                close = hist["Close"]
                d_ret = _compute_return_pct(close, 1)
                w_ret = _compute_return_pct(close, 5)
                m_ret = _compute_return_pct(close, 21)
        except Exception:
            pass

        assets.append(
            {
                "symbol": sym,
                "label": label,
                "d": d_ret,
                "w": w_ret,
                "m": m_ret,
            }
        )

    _INDICES_CACHE_DATA = {"as_of": today.isoformat(), "assets": assets}
    _INDICES_CACHE_TS = now

    return [
        {
            "symbol": a.get("symbol"),
            "name": a.get("label"),
            "daily": a.get("d"),
            "weekly": a.get("w"),
            "monthly": a.get("m"),
        }
        for a in assets
    ]


# ==============================
# /api/macro/calendar (simple)
# ==============================

@router.get("/calendar")
def macro_calendar(
    days_ahead: int = 2,
    impact_filter: Optional[Literal["low", "medium", "high"]] = None,
):
    today = date.today()

    events = [
        {
            "date": today.isoformat(),
            "time": "14:30",
            "event": "CPI US",
            "impact": "high",
            "currency": "USD",
            "country": "US",
        },
        {
            "date": today.isoformat(),
            "time": "16:00",
            "event": "ISM Services",
            "impact": "medium",
            "currency": "USD",
            "country": "US",
        },
        {
            "date": (today + timedelta(days=1)).isoformat(),
            "time": "20:00",
            "event": "Minutes FOMC",
            "impact": "high",
            "currency": "USD",
            "country": "US",
        },
        {
            "date": (today + timedelta(days=2)).isoformat(),
            "time": "10:00",
            "event": "CPI Zone Euro",
            "impact": "high",
            "currency": "EUR",
            "country": "EU",
        },
    ]

    max_date = today + timedelta(days=days_ahead)
    events = [
        e
        for e in events
        if date.fromisoformat(e["date"]) <= max_date
    ]

    if impact_filter:
        events = [e for e in events if e["impact"] == impact_filter]

    events.sort(
        key=lambda e: datetime.combine(
            date.fromisoformat(e["date"]),
            time.fromisoformat(e["time"])
        )
    )

    return events


# ==============================
# /api/macro/sentiment_grid
# ==============================

@router.get("/sentiment_grid")
def macro_sentiment_grid():
    """
    Grille de sentiment news par jour et par thématique
    utilisée par la page MACRO (tableau hebdo).
    """
    today = dt.date.today()
    start = today - dt.timedelta(days=4)  # 5 jours
    end = today

    raw = build_week_raw(start, end)
    grid = raw.get("sentiment_grid", [])

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "grid": grid,
    }
