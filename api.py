# ============================================
#  trading_dashboard / api.py
#  Backend FastAPI pour Stark Trading Dashboard
#  Données temps quasi réel via yfinance
# ============================================

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import yfinance as yf
import time
from typing import Tuple

# --------------------------------------------
# Initialisation FastAPI + CORS
# --------------------------------------------
app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour Stark Trading Dashboard (ES, NQ, BTC, CL, GC)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # pour le dev, on ouvre tout
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------
# Mapping de tes instruments
# --------------------------------------------
INSTRUMENTS = {
    "ES": {
        "yf_symbol": "ES=F",
        "label": "S&P 500 Future",
    },
    "NQ": {
        "yf_symbol": "NQ=F",
        "label": "Nasdaq 100 Future",
    },
    "BTC": {
        "yf_symbol": "BTC-USD",
        "label": "Bitcoin",
    },
    "CL": {
        "yf_symbol": "CL=F",
        "label": "Crude Oil (WTI)",
    },
    "GC": {
        "yf_symbol": "GC=F",
        "label": "Gold",
    },
}


# --------------------------------------------
# Helper : récupère dernier prix + précédent
# avec fallback robuste (fast_info → intraday → daily)
# --------------------------------------------
def get_last_prices(yf_symbol: str) -> Tuple[float, float]:
    """
    Retourne (dernier prix, prix précédent) pour un ticker yfinance.
    Essaie d'abord fast_info, puis history() intraday, puis daily.
    Lève ValueError si aucune donnée fiable.
    """
    ticker = yf.Ticker(yf_symbol)

    # 1) fast_info : très fiable pour le dernier prix / previous_close
    try:
        fi = getattr(ticker, "fast_info", None) or {}
        last_fast = fi.get("last_price")
        prev_fast = fi.get("previous_close")

        if last_fast is not None and prev_fast is not None:
            return float(last_fast), float(prev_fast)
    except Exception:
        # On ne fait pas planter pour fast_info
        pass

    # 2) fallback intraday (2 jours, 1 minute)
    try:
        data = ticker.history(period="2d", interval="1m")
        closes = data.get("Close")
        if closes is not None and not closes.empty and len(closes) >= 2:
            return float(closes.iloc[-1]), float(closes.iloc[-2])
    except Exception:
        pass

    # 3) fallback daily (5 jours, 1 jour)
    try:
        data = ticker.history(period="5d", interval="1d")
        closes = data.get("Close")
        if closes is not None and not closes.empty and len(closes) >= 2:
            return float(closes.iloc[-1]), float(closes.iloc[-2])
    except Exception:
        pass

    # Si on est encore là : rien de fiable
    raise ValueError(f"Données indisponibles pour {yf_symbol}")


# --------------------------------------------
# Helper : génère un petit commentaire FR
# --------------------------------------------
def build_comment(symbol: str, label: str, change_pct: float) -> str:
    base = {
        "ES": "S&P 500 future",
        "NQ": "Nasdaq 100 future",
        "BTC": "Bitcoin",
        "CL": "le pétrole brut",
        "GC": "l'or",
    }.get(symbol, label)

    if abs(change_pct) < 0.1:
        return f"{base} quasi stable"
    elif change_pct > 0:
        if change_pct > 1.5:
            return f"{base} en forte hausse"
        else:
            return f"{base} en légère hausse"
    else:
        if change_pct < -1.5:
            return f"{base} en forte baisse"
        else:
            return f"{base} en légère baisse"


# --------------------------------------------
# Endpoint racine : ping
# --------------------------------------------
@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}


# --------------------------------------------
# Endpoint principal : /latest?symbol=ES
# --------------------------------------------
@app.get("/latest")
async def latest(symbol: str = Query("ES", description="ES, NQ, BTC, CL, GC")):
    symbol = symbol.upper()

    if symbol not in INSTRUMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbole inconnu : {symbol}. Utilise ES, NQ, BTC, CL ou GC.",
        )

    inst = INSTRUMENTS[symbol]
    yf_symbol = inst["yf_symbol"]
    label = inst["label"]

    try:
        last_price, prev_price = get_last_prices(yf_symbol)
    except ValueError as e:
        # Erreur fonctionnelle (pas de données)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Erreur technique
        raise HTTPException(status_code=500, detail=f"Erreur backend : {e}")

    # Variation en %
    if prev_price and prev_price != 0:
        change_pct = (last_price - prev_price) / prev_price * 100.0
    else:
        change_pct = 0.0

    comment = build_comment(symbol, label, change_pct)

    payload = {
        "symbol": symbol,
        "yf_symbol": yf_symbol,
        "label": label,
        "price_usd": round(last_price, 2),
        "change_pct": round(change_pct, 2),
        "timestamp": time.time(),
        "comment": comment,
    }

    return JSONResponse(payload)
