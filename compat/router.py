# compat/router.py

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
import yfinance as yf

from macro.service import ASSETS, build_week_raw, build_week_summary

router = APIRouter()


# =====================================================
# PRIX / DERNIER TICK (yfinance)
# =====================================================

@router.get("/latest")
def latest_price(symbol: str):
    """
    Compatibilité dashboard existant.
    Renvoie un prix "temps réel" approximatif via yfinance.
    """
    sym = symbol.upper()
    cfg = ASSETS.get(sym)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Symbole inconnu: {symbol}")

    try:
        ticker = yf.Ticker(cfg["yf"])
        hist = ticker.history(period="1d", interval="1m")

        if hist.empty:
            price = 0.0
            change_pct = 0.0
        else:
            last = float(hist["Close"].iloc[-1])
            first = float(hist["Close"].iloc[0])
            price = last
            change_pct = (last - first) / first * 100 if first else 0.0

    except Exception as e:
        # On ne casse pas le front : on renvoie un stub propre.
        price = 0.0
        change_pct = 0.0

    return {
        "symbol": sym,
        "label": cfg["name"],
        "price": price,
        "change_pct": change_pct,
        "comment": "Données intraday via Yahoo Finance.",
        "status": "ok",
    }


# =====================================================
# PERF INDICES (redirige vers macro/indices)
# =====================================================

@router.get("/perf/summary")
def perf_summary():
    """
    Ancien endpoint utilisé par le dashboard pour la performance
    des indices.

    On réemballe macro_indices() dans le format attendu par le front :
    { as_of, assets: [ { symbol, label, d, w, m } ] }
    """
    from macro.router import macro_indices

    data = macro_indices()

    assets = []
    for item in data:
        assets.append(
            {
                "symbol": item.get("symbol"),
                "label": item.get("name"),
                "d": float(item.get("daily", 0.0)),
                "w": float(item.get("weekly", 0.0)),
                "m": float(item.get("monthly", 0.0)),
            }
        )

    as_of = date.today().isoformat()

    return {
        "as_of": as_of,
        "assets": assets,
    }


# =====================================================
# MACRO (anciens endpoints)
# =====================================================

@router.get("/api/macro/bias")
def macro_bias():
    """
    Endpoint simple pour le biais global.
    Utilisé par le bandeau du dashboard.
    """
    from macro.router import macro_snapshot
    snap = macro_snapshot()

    return {
        "risk_on": snap["risk_mode"] == "risk_on",
        "volatility": snap["volatility"],
        "comment": snap["comment"],
    }


@router.get("/api/macro/week/summary")
def macro_week_summary():
    """
    Résumé hebdomadaire macro, utilisé par la section du haut.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())   # lundi
    friday = monday + timedelta(days=4)                # vendredi

    return build_week_summary(monday, friday)


@router.get("/api/macro/week/raw")
def macro_week_raw():
    """
    Données brutes hebdo pour la grille de sentiment.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    return build_week_raw(monday, friday)


# =====================================================
# ETAT MACRO GLOBAL POUR loadMacro() (front legacy)
# =====================================================

@router.get("/api/macro/state")
def macro_state():
    """
    Endpoint utilisé par d'anciens fronts.
    On garde un wrapper simple autour de macro_snapshot().
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
