# compat/router.py

from datetime import date, datetime, time, timedelta
from typing import Optional, Literal, List, Dict, Any

import yfinance as yf
from fastapi import APIRouter

from macro.service import build_week_raw, ASSETS

router = APIRouter()


# =====================================================
# PRIX / DERNIER TICK – branché sur yfinance
# =====================================================

@router.get("/latest")
def latest_price(symbol: str):
    """
    Compat dashboard : dernier prix + % variation via yfinance.
    Utilise la config ASSETS de macro/service.py
    """
    sym = symbol.upper()
    cfg = ASSETS.get(sym)
    if not cfg:
        return {
            "symbol": sym,
            "price": 0.0,
            "change_pct": 0.0,
            "status": "unknown_symbol",
        }

    try:
        ticker = yf.Ticker(cfg["yf"])
        hist = ticker.history(period="2d", interval="1d")

        if hist.empty:
            return {
                "symbol": sym,
                "label": cfg["name"],
                "price": 0.0,
                "change_pct": 0.0,
                "status": "no_data",
            }

        last = float(hist["Close"].iloc[-1])
        if len(hist) >= 2:
            prev = float(hist["Close"].iloc[-2])
            change_pct = (last - prev) / prev * 100 if prev else 0.0
        else:
            change_pct = 0.0

        return {
            "symbol": sym,
            "label": cfg["name"],
            "price": last,
            "change_pct": change_pct,
            "comment": "",
            "status": "ok",
        }
    except Exception:
        return {
            "symbol": sym,
            "label": cfg["name"],
            "price": 0.0,
            "change_pct": 0.0,
            "comment": "",
            "status": "error",
        }


# =====================================================
# PERF INDICES (redirige vers macro/indices, formaté)
# =====================================================

@router.get("/perf/summary")
def perf_summary():
    """
    Ancien endpoint utilisé par le dashboard pour la performance
    des indices.

    On réemballe macro_indices() dans un format :
    {
      "as_of": "YYYY-MM-DD",
      "assets": [
        { "symbol", "label", "d", "w", "m" }
      ]
    }
    """
    from macro.router import macro_indices

    raw = macro_indices()
    assets = []
    for row in raw:
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
        "as_of": date.today().isoformat(),
        "assets": assets,
    }


# =====================================================
# MACRO (anciens endpoints simples)
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


# =====================================================
# VUE HEBDO MACRO – summary + raw
# =====================================================

@router.get("/api/macro/week/summary")
def macro_week_summary():
    """
    Résumé hebdo compatible avec le JS de index.html :
    - start / end
    - risk_on (True / False / None)
    - risk_comment
    - top_moves
    - top_events (pour plus tard)
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    raw = build_week_raw(monday, friday)
    perfs = raw.get("asset_performances", [])

    # On regarde surtout ES / NQ pour le mode risk
    equity_symbols = {"ES", "NQ"}
    eq = [p["return_pct"] for p in perfs if p.get("symbol") in equity_symbols]
    avg = sum(eq) / len(eq) if eq else 0.0

    if avg > 0.5:
        risk_flag: Optional[bool] = True
        comment = "Biais global plutôt risk-on cette semaine sur les indices US."
    elif avg < -0.5:
        risk_flag = False
        comment = "Biais global plutôt risk-off cette semaine sur les indices US."
    else:
        risk_flag = None
        comment = "Pas de biais directionnel net dégagé sur la semaine."

    # Top moves (on trie par |performance|)
    sorted_perfs = sorted(
        perfs,
        key=lambda x: abs(x.get("return_pct", 0.0)),
        reverse=True,
    )
    top_moves = []
    for p in sorted_perfs[:3]:
        mv = float(p.get("return_pct") or 0.0)
        top_moves.append(
            {
                "description": f"Mouvement de {mv:+.2f}% sur {p.get('name') or p.get('symbol')}",
                "asset": p.get("symbol") or "?",
                "move_pct": mv,
                "event_id": None,
            }
        )

    return {
        "start": monday.isoformat(),
        "end": friday.isoformat(),
        "risk_on": risk_flag,
        "risk_comment": comment,
        "top_events": [],       # à remplir si on branche un vrai calendrier macro
        "top_moves": top_moves,
        "upcoming_focus": [],
    }


@router.get("/api/macro/week/raw")
def macro_week_raw():
    """
    Flux brut hebdo : performances + sentiment_grid
    utilisé pour la grille 'Indices & sentiment news'.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    return build_week_raw(monday, friday)


# =====================================================
# ETAT MACRO GLOBAL POUR loadMacro() (front)
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
    mode = snap["risk_mode"]

    if mode == "risk_on":
        label = "Risk-On"
    elif mode == "risk_off":
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
