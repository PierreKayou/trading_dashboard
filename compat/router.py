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
    Renvoie un prix fictif (en attendant le vrai flux local).
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
    """
    Ancien endpoint utilisé par le dashboard pour la performance
    des indices.

    On renvoie directement la liste brute renvoyée par macro_indices(),
    pour être compatible avec le front existant.
    """
    from macro.router import macro_indices
    return macro_indices()


# =====================================================
# MACRO (anciens endpoints)
# =====================================================

@router.get("/api/macro/bias")
def macro_bias():
    """
    Endpoint "simple" pour le biais global.
    Utilisé par certaines parties legacy du front.
    """
    from macro.router import macro_snapshot
    snap = macro_snapshot()
    return {
        "bias": snap["risk_mode"],
        "volatility": snap["volatility"],
        "comment": snap["comment"],
    }


@router.get("/api/macro/week/summary")
def macro_week_summary():
    """
    Compat pour la vue hebdomadaire.
    Donne une période de semaine et un petit résumé.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    return {
        "status": "ok",
        "week_start": monday.isoformat(),
        "week_end": friday.isoformat(),
        "summary": "Aucun événement macro majeur identifié pour la semaine.",
        "key_events": [],
        "notable_moves": [],
    }


@router.get("/api/macro/week/raw")
def macro_week_raw():
    """
    Stub pour un éventuel flux macro brut hebdo.
    """
    return {
        "events": [],
        "note": "Raw macro hebdo non disponible pour le moment.",
    }


# =====================================================
# ETAT MACRO GLOBAL POUR loadMacro() (front)
# =====================================================

@router.get("/api/macro/state")
def macro_state():
    """
    Endpoint utilisé par la fonction JS loadMacro().

    Il réemballe la sortie de macro_snapshot() dans une structure :
    - macro_regime { label, confidence, stability }
    - commentary
    - market_bias { equities, indices_us, commodities, crypto }
    """
    from macro.router import macro_snapshot

    snap = macro_snapshot()

    return {
        "macro_regime": {
            "label": "Risk-On" if snap["risk_mode"] == "risk_on" else "Risk-Off",
            "confidence": 0.72,  # stub pour l’instant
            "stability": "stable" if snap["volatility"] != "high" else "fragile",
        },
        "commentary": snap["comment"],
        "market_bias": {
            "equities": snap["bias"].get("equities", "neutral"),
            "indices_us": snap["bias"].get("equities", "neutral"),
            "commodities": snap["bias"].get("commodities", "neutral"),
            "crypto": snap["bias"].get("crypto", "neutral"),
        },
    }
