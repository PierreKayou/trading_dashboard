# compat/router.py

from fastapi import APIRouter

router = APIRouter()


# =====================================================
# PRIX / DERNIER TICK (stub)
# =====================================================

@router.get("/latest")
def latest_price(symbol: str):
    return {
        "symbol": symbol,
        "label": symbol,
        "price": 0.0,
        "change_pct": 0.0,
        "comment": "Pas de commentaire disponible.",
        "status": "stub",
    }


# =====================================================
# PERF INDICES (FIX)
# =====================================================

@router.get("/perf/summary")
def perf_summary():
    """
    Proxy propre vers /api/macro/indices
    Structure STRICTEMENT compatible front.
    """
    try:
        from macro.router import macro_indices
        data = macro_indices()

        # Sécurité : on garantit la structure
        return {
            "as_of": data.get("as_of"),
            "assets": data.get("assets", []),
        }

    except Exception as e:
        # En cas d’erreur, on renvoie une structure valide
        # pour éviter de casser le front
        return {
            "as_of": None,
            "assets": [],
            "error": str(e),
        }


# =====================================================
# MACRO BIAS (legacy)
# =====================================================

@router.get("/api/macro/bias")
def macro_bias():
    from macro.router import macro_snapshot
    snap = macro_snapshot()

    return {
        "risk_on": snap["risk_mode"] == "risk_on",
        "volatility": snap["volatility"],
        "comment": snap["comment"],
    }
