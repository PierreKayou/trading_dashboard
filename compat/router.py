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

    except Exception:
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
# PERF INDICES (tableau du bas) – 100% yfinance
# =====================================================

INDEX_MAP = {
    "SPX": {
        "name": "S&P 500",
        "yf": "^GSPC",
    },
    "NDX": {
        "name": "Nasdaq 100",
        "yf": "^NDX",
    },
    "DAX": {
        "name": "DAX 40",
        "yf": "^GDAXI",
    },
    "CAC40": {
        "name": "CAC 40",
        "yf": "^FCHI",
    },
    "EURUSD": {
        "name": "EUR / USD",
        "yf": "EURUSD=X",
    },
    "USDJPY": {
        "name": "USD / JPY",
        "yf": "USDJPY=X",
    },
    "BTCUSD": {
        "name": "Bitcoin",
        "yf": "BTC-USD",
    },
}


def _compute_perf_for_ticker(yf_symbol: str):
    """
    Calcule les perfs Jour / Semaine / Mois pour un ticker yfinance donné.

    - Jour   : variation vs clôture de la veille
    - Semaine: variation vs clôture 5 séances avant
    - Mois   : variation vs clôture 21 séances avant
    """
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="60d", interval="1d")

        if hist.empty or len(hist) < 2:
            return None, None, None, None

        # Dernière clôture
        last_close = float(hist["Close"].iloc[-1])
        last_date = hist.index[-1].date()

        # Jour : vs veille
        if len(hist) >= 2:
            prev_close = float(hist["Close"].iloc[-2])
            d_ret = (last_close - prev_close) / prev_close * 100 if prev_close else 0.0
        else:
            d_ret = None

        # Semaine : ~ 5 séances avant
        if len(hist) >= 6:
            week_close = float(hist["Close"].iloc[-6])
            w_ret = (last_close - week_close) / week_close * 100 if week_close else 0.0
        else:
            w_ret = None

        # Mois : ~ 21 séances avant
        if len(hist) >= 22:
            month_close = float(hist["Close"].iloc[-22])
            m_ret = (last_close - month_close) / month_close * 100 if month_close else 0.0
        else:
            m_ret = None

        return last_date, d_ret, w_ret, m_ret

    except Exception:
        return None, None, None, None


@router.get("/perf/summary")
def perf_summary():
    """
    Endpoint utilisé par le tableau 'Performance des indices'.

    Format renvoyé :
    {
      "as_of": "YYYY-MM-DD",
      "assets": [
        { "symbol": "...", "label": "...", "d": float|None, "w": float|None, "m": float|None },
        ...
      ]
    }
    """
    assets = []
    as_of_date = None

    for symbol, cfg in INDEX_MAP.items():
        last_date, d_ret, w_ret, m_ret = _compute_perf_for_ticker(cfg["yf"])

        # On garde la date la plus récente trouvée
        if last_date and (as_of_date is None or last_date > as_of_date):
            as_of_date = last_date

        assets.append(
            {
                "symbol": symbol,
                "label": cfg["name"],
                "d": d_ret,
                "w": w_ret,
                "m": m_ret,
            }
        )

    return {
        "as_of": (as_of_date or date.today()).isoformat(),
        "assets": assets,
    }


# =====================================================
# MACRO (anciens endpoints – biais & hebdo)
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
# ETAT MACRO GLOBAL POUR D’ANCIENS FRONTS
# =====================================================

@router.get("/api/macro/state")
def macro_state():
    """
    Endpoint utilisé par d'anciens fronts. On garde un wrapper simple
    autour de macro_snapshot().
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
