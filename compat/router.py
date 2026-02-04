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

    On transforme la sortie de macro_indices() dans le format
    attendu par index.html :
      {
        "as_of": "YYYY-MM-DD",
        "assets": [
          {"symbol", "label", "d", "w", "m"},
          ...
        ]
      }
    """
    from macro.router import macro_indices

    rows = macro_indices()
    today_str = date.today().isoformat()

    assets = []
    for r in rows:
        assets.append(
            {
                "symbol": r.get("symbol"),
                "label": r.get("name") or r.get("symbol"),
                "d": r.get("daily"),
                "w": r.get("weekly"),
                "m": r.get("monthly"),
            }
        )

    return {
        "as_of": today_str,
        "assets": assets,
    }


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
    Adapté au format attendu par index.html
    (start, end, risk_on, risk_comment, top_events, top_moves, upcoming_focus).
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    return {
        "start": monday.isoformat(),
        "end": friday.isoformat(),
        "risk_on": None,
        "risk_comment": "Aucun événement macro majeur identifié pour la semaine.",
        "top_events": [],
        "top_moves": [],
        "upcoming_focus": [],
    }


@router.get("/api/macro/week/raw")
def macro_week_raw():
    """
    Stub pour un éventuel flux macro brut hebdo.
    Le front gère le cas où sentiment_grid est absent.
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

    risk_mode = snap["risk_mode"]
    if risk_mode == "risk_on":
        label = "Risk-On"
    elif risk_mode == "risk_off":
        label = "Risk-Off"
    else:
        label = "Neutre"

    return {
        "macro_regime": {
            "label": label,
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
