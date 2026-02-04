from fastapi import APIRouter
from datetime import datetime, date, time, timedelta
from typing import Optional, Literal

router = APIRouter(prefix="/macro")


# =====================================================
# Types
# =====================================================

RiskMode = Literal["risk_on", "risk_off", "neutral"]
VolatilityLevel = Literal["low", "medium", "high"]


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
# =====================================================

@router.get("/indices")
def macro_indices():
    return [
        {
            "symbol": "SPX",
            "name": "S&P 500",
            "asset_class": "equity",
            "region": "US",
            "daily": 0.8,
            "weekly": 2.1,
            "monthly": 4.3,
        },
        {
            "symbol": "NDX",
            "name": "Nasdaq 100",
            "asset_class": "equity",
            "region": "US",
            "daily": 1.3,
            "weekly": 3.0,
            "monthly": 6.5,
        },
        {
            "symbol": "DAX",
            "name": "DAX 40",
            "asset_class": "equity",
            "region": "EU",
            "daily": 0.4,
            "weekly": 1.2,
            "monthly": 2.8,
        },
        {
            "symbol": "CAC40",
            "name": "CAC 40",
            "asset_class": "equity",
            "region": "EU",
            "daily": 0.3,
            "weekly": 0.9,
            "monthly": 2.1,
        },
        {
            "symbol": "EURUSD",
            "name": "EUR / USD",
            "asset_class": "fx",
            "region": "FX",
            "daily": -0.2,
            "weekly": -0.5,
            "monthly": -1.1,
        },
        {
            "symbol": "USDJPY",
            "name": "USD / JPY",
            "asset_class": "fx",
            "region": "FX",
            "daily": 0.1,
            "weekly": 0.6,
            "monthly": 1.4,
        },
        {
            "symbol": "BTCUSD",
            "name": "Bitcoin",
            "asset_class": "crypto",
            "region": "Crypto",
            "daily": 1.9,
            "weekly": 4.5,
            "monthly": 10.2,
        },
    ]


# =====================================================
# /api/macro/calendar
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
