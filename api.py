# api.py
# ============================================
#  API backend pour ton Trading Dashboard
#  Multi-actifs + prix en USD et EUR
# ============================================

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import yfinance as yf
import time

app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour récupérer les données de marché (USD & EUR)",
    version="1.1"
)

# CORS pour ton frontend (GitHub Pages)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK pour dev, on pourra restreindre plus tard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# Mapping des symboles dashboard -> yfinance
# -------------------------------------------------
SYMBOLS = {
    "ES": {
        "yf": "ES=F",
        "label": "S&P 500 future"
    },
    "NQ": {
        "yf": "NQ=F",
        "label": "Nasdaq 100 future"
    },
    "BTC": {
        "yf": "BTC-USD",
        "label": "Bitcoin"
    },
    "CL": {
        "yf": "CL=F",
        "label": "Crude Oil (WTI)"
    },
    "GC": {
        "yf": "GC=F",
        "label": "Gold"
    },
}

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def get_last_prices(yf_symbol: str) -> tuple[float, float]:
    """
    Retourne (last_price, prev_price) pour un ticker yfinance.
    On essaie d'abord en intraday 1m sur 2 jours,
    puis fallback en daily si besoin.
    """
    ticker = yf.Ticker(yf_symbol)

    data = ticker.history(period="2d", interval="1m")
    if data.empty or len(data["Close"]) < 2:
        data = ticker.history(period="5d", interval="1d")

    if data.empty or len(data["Close"]) < 2:
        raise ValueError(f"Pas assez de données pour {yf_symbol}")

    last_price = float(data["Close"].iloc[-1])
    prev_price = float(data["Close"].iloc[-2])
    return last_price, prev_price


def get_fx_eur_usd() -> float:
    """
    Renvoie EURUSD (USD pour 1 EUR).
    Exemple : 1.08 => 1 EUR = 1.08 USD.
    """
    ticker = yf.Ticker("EURUSD=X")
    data = ticker.history(period="1d", interval="1m")

    if data.empty:
        raise ValueError("Impossible de récupérer EURUSD")

    fx = float(data["Close"].iloc[-1])
    return fx


def build_comment(label: str, change_pct: float) -> str:
    """Petit commentaire auto en fonction de la variation."""
    if change_pct > 1.0:
        return f"{label} en forte hausse"
    elif change_pct > 0.2:
        return f"{label} en légère hausse"
    elif change_pct < -1.0:
        return f"{label} en forte baisse"
    elif change_pct < -0.2:
        return f"{label} en légère baisse"
    else:
        return f"{label} quasi stable"


# -------------------------------------------------
# Endpoint de test
# -------------------------------------------------
@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}


# -------------------------------------------------
# Endpoint principal : /latest?symbol=ES
# -------------------------------------------------
@app.get("/latest")
async def latest(symbol: str = Query("ES")):
    """
    Renvoie les données temps réel pour un actif :
    - price_usd
    - price_eur (via EURUSD)
    - change_pct (en %)
    - commentaire court
    """

    code = symbol.upper()
    if code not in SYMBOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbole inconnu : {code}"
        )

    cfg = SYMBOLS[code]

    try:
        # Prix en USD
        last_usd, prev_usd = get_last_prices(cfg["yf"])
        change_pct = (last_usd - prev_usd) / prev_usd * 100 if prev_usd else 0.0

        # FX EURUSD (USD pour 1 EUR)
        fx_eur_usd = get_fx_eur_usd()
        price_eur = last_usd / fx_eur_usd if fx_eur_usd else None

        comment = build_comment(cfg["label"], change_pct)

        payload = {
            "symbol": code,
            "yf_symbol": cfg["yf"],
            "label": cfg["label"],
            "price_usd": round(last_usd, 2),
            "price_eur": round(price_eur, 2) if price_eur is not None else None,
            "currency": "USD",              # devise native des prix
            "change_pct": round(change_pct, 2),
            "fx_eur_usd": round(fx_eur_usd, 5),
            "timestamp": time.time(),
            "comment": comment,
        }

        return JSONResponse(payload)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération données pour {code} : {e}"
        )
