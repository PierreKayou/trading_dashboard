###############################
# econ_calendar/router.py
###############################
from fastapi import APIRouter, HTTPException
import os
import time
import datetime as dt
import requests

router = APIRouter(prefix="/calendar", tags=["calendar"])

FMP_API_KEY = os.getenv("FMP_API_KEY")

# Cache simple pour limiter les appels API au calendrier FMP.
_CALENDAR_CACHE_DATA: dict | None = None
_CALENDAR_CACHE_KEY: tuple[dt.date, dt.date] | None = None
_CALENDAR_CACHE_TS: float = 0.0
_CALENDAR_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_calendar_with_cache(today: dt.date, week_end: dt.date) -> dict:
    """
    Retourne un dictionnaire standardisé :
    {
        "source": "fmp" | "mock",
        "fetched_at": timestamp,
        "today_events": [...],
        "week_events": [...],
    }
    en utilisant un cache in-memory basique.
    """
    global _CALENDAR_CACHE_DATA, _CALENDAR_CACHE_KEY, _CALENDAR_CACHE_TS

    now = time.time()
    key = (today, week_end)

    if (
        _CALENDAR_CACHE_DATA is not None
        and _CALENDAR_CACHE_KEY == key
        and now - _CALENDAR_CACHE_TS < _CALENDAR_CACHE_TTL_SECONDS
    ):
        return _CALENDAR_CACHE_DATA

    if FMP_API_KEY:
        raw = _fetch_from_fmp(today, week_end)
        today_events, week_events = _normalize_events(raw, today)
        source = "fmp"
    else:
        today_events, week_events = _mock_events(today)
        source = "mock"

    data = {
        "source": source,
        "fetched_at": time.time(),
        "today_events": today_events,
        "week_events": week_events,
    }

    _CALENDAR_CACHE_DATA = data
    _CALENDAR_CACHE_KEY = key
    _CALENDAR_CACHE_TS = now

    return data


def _fetch_from_fmp(start: dt.date, end: dt.date):
    """
    Appel brut à l'API Economic Calendar de FMP.
    Docs : https://financialmodelingprep.com/stable/economic-calendar
    """
    if not FMP_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="FMP_API_KEY non configuré sur le serveur.",
        )

    url = "https://financialmodelingprep.com/stable/economic-calendar"
    params = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "apikey": FMP_API_KEY,
    }

    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Erreur FMP: {resp.text}",
        )

    return resp.json()


def _normalize_events(raw, today: dt.date):
    """
    Normalise le format de FMP vers un format commun.
    """
    if not isinstance(raw, list):
        raw = []

    events = []

    for item in raw:
        try:
            date_str = item.get("date")
            time_str = item.get("time", "") or ""
            country = item.get("country", "")
            event_name = item.get("event", "")
            impact = (item.get("impact", "") or "").lower()

            if not date_str or not event_name:
                continue

            # On ne garde que les évènements ayant un impact renseigné
            if impact not in ["low", "medium", "high"]:
                impact = "medium"

            events.append(
                {
                    "date": date_str,
                    "time": time_str,
                    "country": country,
                    "event": event_name,
                    "impact": impact,
                    "actual": item.get("actual"),
                    "previous": item.get("previous"),
                    "consensus": item.get("estimate") or item.get("consensus"),
                }
            )
        except Exception:
            continue

    today_str = today.isoformat()
    today_events = [e for e in events if e["date"] == today_str]
    week_events = [e for e in events if e["date"] != today_str]

    # On trie par date/heure
    def sort_key(e):
        return (e["date"], e["time"] or "")

    today_events.sort(key=sort_key)
    week_events.sort(key=sort_key)

    return today_events, week_events


def _mock_events(today: dt.date):
    """
    Fallback si aucun FMP_API_KEY : petits events fictifs pour garder le UX propre.
    """
    return _normalize_events(
        [
            {
                "date": today.isoformat(),
                "time": "14:30",
                "country": "US",
                "event": "CPI US (YoY)",
                "impact": "high",
                "actual": None,
                "previous": None,
                "consensus": None,
            },
            {
                "date": today.isoformat(),
                "time": "16:00",
                "country": "US",
                "event": "ISM Services",
                "impact": "medium",
                "actual": None,
                "previous": None,
                "consensus": None,
            },
            {
                "date": (today + dt.timedelta(days=1)).isoformat(),
                "time": "20:00",
                "country": "US",
                "event": "Minutes FOMC",
                "impact": "high",
                "actual": None,
                "previous": None,
                "consensus": None,
            },
            {
                "date": (today + dt.timedelta(days=2)).isoformat(),
                "time": "10:00",
                "country": "EU",
                "event": "CPI Zone Euro",
                "impact": "high",
                "actual": None,
                "previous": None,
                "consensus": None,
            },
        ],
        today,
    )


# =====================================================
# Vue synthétique /summary (macro.html, API, etc.)
# =====================================================

@router.get("/summary")
async def get_calendar_summary():
    """
    Vue synthétique calendrier économique :
    - today : évènements du jour
    - next_days : évènements des 6 prochains jours
    """
    today = dt.date.today()
    week_end = today + dt.timedelta(days=6)

    data = _get_calendar_with_cache(today, week_end)

    return {
        "source": data["source"],
        "fetched_at": data["fetched_at"],
        "today": data["today_events"],
        "next_days": data["week_events"],  # clé alignée avec le front macro.html
        "week": data["week_events"],       # optionnel, pour débogage
    }


# =====================================================
# Endpoints compatibles avec index.html
#  - /api/calendar/today → { events: [...] }
#  - /api/calendar/next  → { events: [...] }
# =====================================================

@router.get("/today")
async def get_calendar_today():
    today = dt.date.today()
    week_end = today + dt.timedelta(days=6)

    data = _get_calendar_with_cache(today, week_end)

    return {
        "source": data["source"],
        "fetched_at": data["fetched_at"],
        "events": data["today_events"],
    }


@router.get("/next")
async def get_calendar_next():
    today = dt.date.today()
    week_end = today + dt.timedelta(days=6)

    data = _get_calendar_with_cache(today, week_end)

    return {
        "source": data["source"],
        "fetched_at": data["fetched_at"],
        "events": data["week_events"],
    }
