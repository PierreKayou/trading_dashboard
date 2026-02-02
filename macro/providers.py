# macro/providers.py

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

import httpx

from .schemas import (
    MacroEvent,
    NewsItem,
    AssetPerformance,
    SentimentCell,
    SentimentBucket,
    MacroSeries,
    MacroSeriesPoint,
    CountryMacroSnapshot,
    MonthlyAssetPerformance,
    ThemeFrequency,
)


def _get_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


FINNHUB_API_KEY = _get_env("FINNHUB_API_KEY")
FRED_API_KEY = _get_env("FRED_API_KEY")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _importance_from_finnhub(impact: Optional[str]) -> str:
    if not impact:
        return "medium"
    impact = impact.lower()
    if "high" in impact:
        return "high"
    if "low" in impact:
        return "low"
    return "medium"


def _category_from_event_name(name: str) -> str:
    n = name.lower()
    if "cpi" in n or "inflation" in n or "price index" in n:
        return "inflation"
    if "employment" in n or "unemployment" in n or "jobs" in n or "payrolls" in n:
        return "employment"
    if "rate decision" in n or "interest rate" in n or "fomc" in n or "ecb" in n:
        return "central_bank"
    if "gdp" in n or "growth" in n:
        return "growth"
    if "confidence" in n or "sentiment" in n:
        return "sentiment"
    return "other"


def _bucket_from_news(news: NewsItem) -> SentimentBucket:
    h = news.headline.lower()
    if "fed" in h or "fomc" in h or "cpi" in h or "jobs" in h or "unemployment" in h:
        return "macro_us"
    if "ecb" in h or "euro" in h or "europe" in h or "germany" in h or "france" in h:
        return "macro_europe"
    if "earnings" in h or "results" in h or "guidance" in h or "company" in h:
        return "companies"
    if "war" in h or "conflict" in h or "sanction" in h or "geopolit" in h:
        return "geopolitics"
    if "ai" in h or "chip" in h or "semiconductor" in h or "tech" in h:
        return "tech"
    return "macro_us"


def _demo_asset_performances(period: str) -> List[AssetPerformance]:
    if period == "week":
        return [
            AssetPerformance(symbol="ES", name="S&P 500 Futures", period="week", return_pct=1.8),
            AssetPerformance(symbol="NQ", name="Nasdaq 100 Futures", period="week", return_pct=2.4),
            AssetPerformance(symbol="DAX", name="DAX Index", period="week", return_pct=0.9),
            AssetPerformance(symbol="CAC", name="CAC 40", period="week", return_pct=0.7),
            AssetPerformance(symbol="VIX", name="VIX Index", period="week", return_pct=-10.2),
        ]
    if period == "month":
        return [
            MonthlyAssetPerformance(symbol="ES", name="S&P 500 Futures", asset_class="equity", return_pct=3.2),
            MonthlyAssetPerformance(symbol="NQ", name="Nasdaq 100 Futures", asset_class="equity", return_pct=4.5),
            MonthlyAssetPerformance(symbol="DAX", name="DAX Index", asset_class="equity", return_pct=2.1),
            MonthlyAssetPerformance(symbol="CAC", name="CAC 40", asset_class="equity", return_pct=1.8),
            MonthlyAssetPerformance(symbol="DXY", name="Dollar Index", asset_class="fx", return_pct=-0.6),
            MonthlyAssetPerformance(symbol="GC", name="Gold Futures", asset_class="commodity", return_pct=1.1),
            MonthlyAssetPerformance(symbol="CL", name="Crude Oil", asset_class="commodity", return_pct=-2.3),
        ]
    return []


# ---------------------------------------------------------------------------
# Finnhub – Economic calendar & news
# ---------------------------------------------------------------------------

async def fetch_economic_calendar_week(start: date, end: date) -> List[MacroEvent]:
    """
    Récupère le calendrier économique via Finnhub si FINNHUB_API_KEY est défini.
    Sinon, renvoie un jeu de données de démonstration.
    """
    if not FINNHUB_API_KEY:
        # Demo data
        base_dt = datetime.combine(start, datetime.min.time())
        return [
            MacroEvent(
                id="demo_cpi_us",
                datetime=base_dt.replace(hour=14),
                country="US",
                importance="high",
                category="inflation",
                title="US CPI (YoY)",
                actual=None,
                previous=3.4,
                consensus=3.2,
                unit="%",
                impact_asset="ES",
                impact_move_pct=-1.5,
            ),
            MacroEvent(
                id="demo_nfp",
                datetime=base_dt.replace(day=start.day + 2, hour=14, minute=30),
                country="US",
                importance="high",
                category="employment",
                title="Non-Farm Payrolls",
                actual=None,
                previous=180_000,
                consensus=200_000,
                unit="jobs",
                impact_asset="ES",
                impact_move_pct=1.2,
            ),
            MacroEvent(
                id="demo_ecb",
                datetime=base_dt.replace(day=start.day + 3, hour=13, minute=45),
                country="EU",
                importance="high",
                category="central_bank",
                title="ECB Rate Decision",
                unit="%",
                impact_asset="ESTX50",
                impact_move_pct=-0.8,
            ),
        ]

    url = "https://finnhub.io/api/v1/calendar/economic"
    params = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "token": FINNHUB_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    events: List[MacroEvent] = []
    for item in data.get("economicCalendar", []):
        try:
            dt_str = f"{item.get('date')} {item.get('time') or '00:00'}"
            dt = datetime.fromisoformat(dt_str.replace(" ", "T"))
        except Exception:
            continue

        title = item.get("event") or "Unknown"
        country = item.get("country", "US")
        impact = _importance_from_finnhub(item.get("impact"))
        category = _category_from_event_name(title)

        actual = item.get("actual")
        previous = item.get("previous")
        estimate = item.get("estimate")

        macro_event = MacroEvent(
            id=f"{country}_{title}_{item.get('date')}_{item.get('time')}",
            datetime=dt,
            country=country,
            importance=impact,  # type: ignore[arg-type]
            category=category,  # type: ignore[arg-type]
            title=title,
            actual=float(actual) if isinstance(actual, (int, float)) else None,
            previous=float(previous) if isinstance(previous, (int, float)) else None,
            consensus=float(estimate) if isinstance(estimate, (int, float)) else None,
            unit=item.get("unit"),
        )
        events.append(macro_event)

    return events


async def fetch_news_for_period(start: date, end: date) -> List[NewsItem]:
    """
    Récupère quelques news générales via Finnhub.
    Demo data si pas d'API key.
    """
    if not FINNHUB_API_KEY:
        now = datetime.utcnow()
        return [
            NewsItem(
                id="demo_news_1",
                datetime=now - timedelta(days=2),
                source="DemoWire",
                headline="Fed hints at slower pace of rate hikes amid cooling inflation",
                url="https://example.com/news1",
                tickers=["ES", "NQ"],
                sentiment=0.3,
                category="macro",
            ),
            NewsItem(
                id="demo_news_2",
                datetime=now - timedelta(days=1),
                source="DemoWire",
                headline="Tech megacaps extend rally on strong AI demand",
                url="https://example.com/news2",
                tickers=["NQ"],
                sentiment=0.6,
                category="tech",
            ),
            NewsItem(
                id="demo_news_3",
                datetime=now - timedelta(days=3),
                source="DemoWire",
                headline="Geopolitical tensions rise in key oil-producing region",
                url="https://example.com/news3",
                tickers=["CL"],
                sentiment=-0.4,
                category="geopolitics",
            ),
        ]

    # Simplement on va chercher des news "general" sur la période
    url = "https://finnhub.io/api/v1/news"
    params = {"category": "general", "token": FINNHUB_API_KEY}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    news_items: List[NewsItem] = []
    for item in data:
        try:
            dt = datetime.fromisoformat(item.get("datetime_iso") or "")
        except Exception:
            # fallback unix timestamp si dispo
            ts = item.get("datetime")
            if isinstance(ts, (int, float)):
                dt = datetime.utcfromtimestamp(ts)
            else:
                continue

        if dt.date() < start or dt.date() > end:
            continue

        headline = item.get("headline") or "No title"
        url_item = item.get("url") or "https://example.com/news"
        source = item.get("source") or "Unknown"

        n = NewsItem(
            id=str(item.get("id") or f"{source}_{dt.isoformat()}"),
            datetime=dt,
            source=source,
            headline=headline,
            url=url_item,
            tickers=item.get("related", "").split(",") if item.get("related") else [],
            # Finnhub ne donne pas directement un sentiment → None pour l'instant
            sentiment=None,
            category="macro",
        )
        news_items.append(n)

    return news_items


# ---------------------------------------------------------------------------
# FRED – séries macro (CPI, taux, etc.)
# ---------------------------------------------------------------------------

async def fetch_fred_series(
    series_id: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> MacroSeries:
    """
    Récupère une série simple depuis FRED.
    Demo data si pas de FRED_API_KEY.
    """
    if not FRED_API_KEY:
        # Démo : petite série mensuelle artificielle
        today = date.today().replace(day=1)
        points: List[MacroSeriesPoint] = []
        for i in range(12):
            d = (today.replace(day=1) - timedelta(days=30 * (11 - i)))
            points.append(MacroSeriesPoint(date=d, value=100 + i * 0.5))
        return MacroSeries(name=series_id, label=series_id, points=points)

    url = "https://api.stlouisfed.org/fred/series/observations"
    params: Dict[str, Any] = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
    }
    if start:
        params["observation_start"] = start.isoformat()
    if end:
        params["observation_end"] = end.isoformat()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    points: List[MacroSeriesPoint] = []
    for obs in data.get("observations", []):
        d_str = obs.get("date")
        v_str = obs.get("value")
        if not d_str or not v_str:
            continue
        try:
            d = date.fromisoformat(d_str)
            v = float(v_str)
        except Exception:
            continue
        points.append(MacroSeriesPoint(date=d, value=v))

    return MacroSeries(name=series_id, label=series_id, points=points)


# ---------------------------------------------------------------------------
# Helpers pour la vue "mois / contexte"
# ---------------------------------------------------------------------------

async def fetch_country_snapshots_demo() -> List[CountryMacroSnapshot]:
    # Pour l’instant on fait un snapshot démo.
    return [
        CountryMacroSnapshot(
            country="US",
            inflation=3.1,
            policy_rate=5.25,
            unemployment=3.8,
            gdp_growth=2.1,
        ),
        CountryMacroSnapshot(
            country="Euro Area",
            inflation=2.7,
            policy_rate=4.00,
            unemployment=6.5,
            gdp_growth=0.9,
        ),
        CountryMacroSnapshot(
            country="UK",
            inflation=3.5,
            policy_rate=5.25,
            unemployment=4.2,
            gdp_growth=0.8,
        ),
        CountryMacroSnapshot(
            country="Japan",
            inflation=2.2,
            policy_rate=0.10,
            unemployment=2.6,
            gdp_growth=1.0,
        ),
        CountryMacroSnapshot(
            country="China",
            inflation=0.4,
            policy_rate=3.45,
            unemployment=5.1,
            gdp_growth=4.9,
        ),
    ]


async def build_theme_frequencies_demo() -> List[ThemeFrequency]:
    return [
        ThemeFrequency(theme="taux", count=18),
        ThemeFrequency(theme="inflation", count=14),
        ThemeFrequency(theme="guerre", count=9),
        ThemeFrequency(theme="tech AI", count=11),
        ThemeFrequency(theme="banques", count=5),
    ]
