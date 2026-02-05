# macro/router.py

from fastapi import APIRouter
from datetime import datetime, date, time, timedelta
from typing import Optional, Literal

import datetime as dt
import yfinance as yf

router = APIRouter(prefix="/macro")


# =====================================================
# Types
# =====================================================

RiskMode = Literal["risk_on", "risk_off", "neutral"]
VolatilityLevel = Literal["low", "medium", "high"]


# =====================================================
# Helpers indices (yfinance)
# =====================================================

# Mapping indice / ticker Yahoo Finance
INDEX_SYMBOLS = {
    "SPX": {"label": "S&P 500", "yf": "^GSPC"},
    "NDX": {"label": "Nasdaq 100", "yf": "^NDX"},
    "DAX": {"label": "DAX 40", "yf": "^GDAXI"},
    "CAC40": {"label": "CAC 40", "yf": "^FCHI"},
    "EURUSD": {"label": "EUR / USD", "yf": "EURUSD=X"},
    "USDJPY": {"label": "USD / JPY", "yf": "JPY=X"},
    "BTCUSD": {"label": "Bitcoin", "yf": "BTC-USD"},
}


def _compute_return_pct(close_series, periods: int) -> Optional[float]:
    """
    Calcule la variation en % entre la dernière clôture
    et la clôture N périodes avant (1 jour, 5 jours, 21 jours, etc.).
    """
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


# =====================================================
# /api/macro/snapshot
# =====================================================

@router.get("/snapshot")
def macro_snapshot():
    now = datetime.utcnow()

    return {
        "timestamp": now.isoformat(),
        "risk_mode": "risk_on",
        "volatility": "medium",
        "bias": {
            "equities": "bullish",
            "rates": "bearish",
            "usd": "strong",
            "credit": "stable",
            "commodities": "neutral",
            "crypto": "neutral",
        },
        "comment": (
            "Momentum positif sur les indices US et EU, "
            "volatilité contenue, dollar toujours ferme."
        ),
    }


# =====================================================
# /api/macro/orientation
# =====================================================

@router.get("/orientation")
def macro_orientation():
    now = datetime.utcnow()

    return {
        "timestamp": now.isoformat(),
        "risk": "on",
        "confidence": 0.78,
        "comment": "Contexte global risk-on confirmé.",
        "notes": [
            "VIX < 20",
            "Aucun stress crédit visible",
            "USD fort mais stable",
        ],
    }


# =====================================================
# /api/macro/indices
#   → utilisé via /perf/summary (compat.router)
#   → renvoie { as_of, assets: [...] } pour le front
# =====================================================

@router.get("/indices")
def macro_indices():
    """
    Performance des grands indices (Jour / Semaine / Mois),
    calculée directement via yfinance.

    Retour :
    {
        "as_of": "YYYY-MM-DD",
        "assets": [
            { "symbol": "SPX", "label": "S&P 500", "d": 0.8, "w": 2.1, "m": 4.3 },
            ...
        ]
    }
    """
    today = dt.date.today()
    # On prend ~2 mois d'historique pour être tranquille
    start = today - dt.timedelta(days=60)

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
                # 1 jour / 5 jours / 21 jours ouvrés approximatifs
                d_ret = _compute_return_pct(close, 1)
                w_ret = _compute_return_pct(close, 5)
                m_ret = _compute_return_pct(close, 21)
        except Exception:
            # En cas d'erreur réseau/API on laisse les valeurs à None
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

    return {
        "as_of": today.isoformat(),
        "assets": assets,
    }


# =====================================================
# /api/macro/calendar
#   (ancien calendrier simple, conservé pour compat éventuelle)
# =====================================================

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
            "time": "11:00",
            "event": "Décision BCE",
            "impact": "high",
            "currency": "EUR",
            "country": "EU",
        },
    ]

    max_date = today + timedelta(days=days_ahead)

    events = [
        e for e in events
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
