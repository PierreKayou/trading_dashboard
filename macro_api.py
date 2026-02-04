# macro_api.py
from fastapi import APIRouter
from datetime import datetime, date, time, timedelta
from typing import List, Literal, Optional

router = APIRouter(
    prefix="/macro",
    tags=["macro"],
)

RiskMode = Literal["risk_on", "risk_off", "neutral"]
VolatilityLevel = Literal["low", "medium", "high"]


# =========================
#  /macro/snapshot
# =========================
@router.get("/snapshot")
def get_macro_snapshot():
    """
    Vue macro globale – stable, simple, exploitable par l'app locale.
    Pour l'instant : données mockées, à brancher plus tard sur tes vraies sources.
    """
    now = datetime.utcnow()

    # TODO: à remplacer plus tard par une vraie logique (yfinance, VIX, etc.)
    snapshot = {
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
            "Les indices actions montrent un momentum positif, volatilité contenue, "
            "dollar fort contre les principales devises."
        ),
    }
    return snapshot


# =========================
#  /macro/orientation
# =========================
@router.get("/orientation")
def get_macro_orientation():
    """
    End point ultra simple pour les bots / app locale.
    """
    now = datetime.utcnow()

    # TODO: brancher sur un modèle IA + indicateurs réels
    orientation = {
        "timestamp": now.isoformat(),
        "risk": "on",          # "on", "off" ou "neutral"
        "confidence": 0.78,    # entre 0 et 1
        "comment": (
            "Contexte global risk-on : flux acheteurs sur indices US et Europe, "
            "pas de stress majeur sur le marché du crédit."
        ),
        "notes": [
            "VIX sous 20.",
            "Spread crédit investment grade stable.",
            "USD légèrement surévalué mais toujours fort."
        ],
    }
    return orientation


# =========================
#  /macro/indices
# =========================
@router.get("/indices")
def get_macro_indices():
    """
    Tableau de performances des indices / devises / symboles majeurs.
    Pour l'instant mocké, à brancher ensuite sur yfinance ou autre source.
    """
    # TODO: remplacer ces mocks par de vraies données
    indices = [
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
    return indices


# =========================
#  /macro/calendar
# =========================
@router.get("/calendar")
def get_macro_calendar(
    days_ahead: int = 2,
    impact_filter: Optional[Literal["low", "medium", "high"]] = None,
):
    """
    Calendrier économique simplifié.
    - days_ahead : nombre de jours à partir d'aujourd'hui (UTC)
    - impact_filter : filtre sur l'impact ("low", "medium", "high")
    Pour l'instant : événements mockés.
    """

    today = date.today()
    day1 = today
    day2 = today + timedelta(days=1)
    day3 = today + timedelta(days=2)

    # TODO: plus tard : remplacer par une vraie source (API calendrier éco)
    events = [
        {
            "date": day1.isoformat(),
            "time": "13:30",
            "event": "CPI (YoY)",
            "impact": "high",
            "currency": "USD",
            "country": "US",
            "description": "Indice des prix à la consommation",
        },
        {
            "date": day1.isoformat(),
            "time": "15:00",
            "event": "ISM Services PMI",
            "impact": "medium",
            "currency": "USD",
            "country": "US",
            "description": "Indice ISM des services",
        },
        {
            "date": day2.isoformat(),
            "time": "10:00",
            "event": "PMI Manufacturier",
            "impact": "medium",
            "currency": "EUR",
            "country": "EU",
            "description": "PMI manufacturier zone euro",
        },
        {
            "date": day2.isoformat(),
            "time": "11:00",
            "event": "Décision de la BCE",
            "impact": "high",
            "currency": "EUR",
            "country": "EU",
            "description": "Annonce taux directeur BCE",
        },
        {
            "date": day3.isoformat(),
            "time": "08:00",
            "event": "GDP (QoQ)",
            "impact": "high",
            "currency": "GBP",
            "country": "UK",
            "description": "Croissance du PIB trimestriel",
        },
    ]

    # Filtre sur horizon (days_ahead)
    max_date = today + timedelta(days=days_ahead)
    events = [
        e for e in events
        if date.fromisoformat(e["date"]) <= max_date
    ]

    # Filtre impact si demandé
    if impact_filter is not None:
        events = [e for e in events if e["impact"] == impact_filter]

    # Tri date + heure
    def sort_key(e):
        d = date.fromisoformat(e["date"])
        h, m = map(int, e["time"].split(":"))
        return datetime.combine(d, time(hour=h, minute=m))

    events.sort(key=sort_key)
    return events
