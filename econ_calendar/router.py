###############################
# econ_calendar/router.py
###############################
from fastapi import APIRouter, HTTPException
import os
import time
import datetime as dt
import requests

router = APIRouter(
    prefix="/calendar",
    tags=["Economic calendar"],
)

FMP_API_KEY = os.getenv("FMP_API_KEY")  # à mettre dans Render si tu veux du vrai flux


def _fetch_from_fmp(start: dt.date, end: dt.date):
    """
    Appelle l'API Financial Modeling Prep pour le calendrier éco.
    Docs : https://financialmodelingprep.com/stable/economic-calendar
    """
    if not FMP_API_KEY:
        return None

    url = "https://financialmodelingprep.com/stable/economic-calendar"
    params = {
        "from": start.isoformat(),
        "to": end.isoformat(),
    }
    headers = {
        "apikey": FMP_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur appel FMP : {e}")

    if not resp.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur API calendrier (FMP) : HTTP {resp.status_code}",
        )

    try:
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"JSON calendrier invalide : {e}")


def _normalize_events(raw_events, today: dt.date):
    """
    On normalise le format des évènements pour le frontend.
    """
    events = []

    for ev in raw_events or []:
        # FMP renvoie habituellement "date" et "time"
        date_str = ev.get("date") or ev.get("dateTime") or ""
        time_str = ev.get("time") or ""

        # On force le format YYYY-MM-DD
        try:
            if date_str:
                date_only = date_str[:10]
            else:
                date_only = today.isoformat()
        except Exception:
            date_only = today.isoformat()

        impact = ev.get("impact") or ev.get("importance") or ""
        if impact:
            impact = impact.lower()

        events.append(
            {
                "date": date_only,  # "2026-02-02"
                "time": time_str or None,
                "country": ev.get("country") or ev.get("region") or None,
                "event": ev.get("event") or ev.get("title") or "Évènement économique",
                "impact": impact or None,  # "low" | "medium" | "high" | ...
                "actual": ev.get("actual"),
                "previous": ev.get("previous"),
                "consensus": ev.get("estimate") or ev.get("consensus"),
            }
        )

    # Split today / reste de la semaine
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
                "event": "NFP (emploi non agricole)",
                "impact": "high",
                "actual": None,
                "previous": None,
                "consensus": None,
            },
            {
                "date": today.isoformat(),
                "time": "16:00",
                "country": "US",
                "event": "ISM manufacturier",
                "impact": "medium",
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


@router.get("/summary")
def get_calendar_summary():
    """
    Vue synthétique calendrier économique :
    - today : évènements du jour
    - week : évènements des 6 prochains jours
    """
    today = dt.date.today()
    week_end = today + dt.timedelta(days=6)

    if FMP_API_KEY:
        raw = _fetch_from_fmp(today, week_end)
        today_events, week_events = _normalize_events(raw, today)
        source = "fmp"
    else:
        today_events, week_events = _mock_events(today)
        source = "mock"

    return {
        "source": source,
        "fetched_at": time.time(),
        "today": today_events,
        "week": week_events,
    }
