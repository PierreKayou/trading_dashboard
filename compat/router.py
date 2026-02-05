from datetime import date, datetime, time, timedelta
from typing import Optional, Literal

from fastapi import APIRouter

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

    On wrappe la sortie de macro_indices() dans un objet
    { as_of: ..., assets: [...] } au format attendu par index.html.
    """
    from macro.router import macro_indices

    indices = macro_indices()
    today = date.today().isoformat()

    assets = []
    for row in indices:
        assets.append(
            {
                "symbol": row.get("symbol"),
                "label": row.get("name") or row.get("symbol"),
                "d": row.get("daily"),
                "w": row.get("weekly"),
                "m": row.get("monthly"),
            }
        )

    return {
        "as_of": today,
        "assets": assets,
    }


# =====================================================
# MACRO (anciens endpoints semaine - formaté pour index.html)
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
    Compat pour la vue hebdomadaire dans index.html.

    Retourne le format attendu par :
      - setWeekRange(summary)  -> summary.start / summary.end
      - setRiskPillWeekly()   -> summary.risk_on
      - renderRiskComment()   -> summary.risk_comment
      - renderTopEvents()     -> summary.top_events
      - renderTopMoves()      -> summary.top_moves
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    return {
        "start": monday.isoformat(),
        "end": friday.isoformat(),
        "risk_on": None,  # neutre par défaut
        "risk_comment": "Aucun événement macro majeur identifié pour la semaine.",
        "top_events": [],
        "top_moves": [],
        "upcoming_focus": [],
    }


@router.get("/api/macro/week/raw")
def macro_week_raw():
    """
    Stub pour un flux macro brut hebdo, compatible avec renderSentimentGrid().
    On renvoie une structure vide mais bien typée.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    return {
        "start": monday.isoformat(),
        "end": friday.isoformat(),
        "created_at": datetime.utcnow().timestamp(),
        "asset_performances": [],
        "sentiment_grid": [],
    }


# =====================================================
# ETAT MACRO GLOBAL POUR loadMacro() (front simple /static)
# =====================================================

@router.get("/api/macro/state")
def macro_state():
    """
    Endpoint utilisé par la fonction JS loadMacro() (static/app.js).

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
