from fastapi import APIRouter
from datetime import date, timedelta

router = APIRouter()


# =====================================================
# PRIX / DERNIER TICK (stub pour le dashboard)
# =====================================================

@router.get("/latest")
def latest_price(symbol: str):
    """
    Compatibilité dashboard existant.
    Renvoie un prix fictif (en attendant flux réel).
    """
    return {
        "symbol": symbol,
        "price": 0.0,
        "change_pct": 0.0,
        "status": "stub",
    }


# =====================================================
# PERF INDICES (redirige vers macro/indices)
# =====================================================

@router.get("/perf/summary")
def perf_summary():
    from macro.router import macro_indices
    data = macro_indices()
    return {
        "indices": data
    }



# =====================================================
# MACRO (anciens endpoints)
# =====================================================

@router.get("/api/macro/bias")
def macro_bias():
    from macro.router import macro_snapshot
    snap = macro_snapshot()
    return {
        "bias": snap["risk_mode"],
        "volatility": snap["volatility"],
        "comment": snap["comment"],
    }

@router.get("/api/macro/week/summary")
def macro_week_summary():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    return {
        "status": "ok",

        # formats possibles attendus par le front
        "week_start": monday.isoformat(),
        "week_end": friday.isoformat(),

        "start_date": monday.isoformat(),
        "end_date": friday.isoformat(),

        "from": monday.isoformat(),
        "to": friday.isoformat(),

        # version déjà lisible si le front affiche direct
        "period": f"Semaine du {monday.strftime('%d/%m')} au {friday.strftime('%d/%m')}",

        "summary": "Aucun événement macro majeur identifié pour la semaine.",
        "key_events": [],
        "notable_moves": [],
    }




@router.get("/api/macro/week/raw")
def macro_week_raw():
    return {
        "events": [],
        "note": "Raw macro hebdo non disponible pour le moment.",
    }


# =====================================================
# CALENDRIER (anciens chemins)
# =====================================================

@router.get("/api/calendar/today")
@router.get("/calendar/today")
def calendar_today():
    from macro.router import macro_calendar
    return macro_calendar(days_ahead=0)


@router.get("/api/calendar/next")
@router.get("/calendar/next")
def calendar_next():
    from macro.router import macro_calendar
    return macro_calendar(days_ahead=2)


# =====================================================
# NEWS IA (stub)
# =====================================================

@router.post("/api/news/analyze")
def news_analyze():
    return {
        "status": "pending",
        "message": "Analyse news IA non encore branchée.",
    }
