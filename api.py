# ============================================
#  trading_dashboard / api.py
#  API backend pour ton dashboard Trading
#  (données réelles via Yahoo Finance)
# ============================================

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import time
import yfinance as yf

app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour récupérer les données de marché (Yahoo Finance)",
    version="1.0"
)

# CORS pour autoriser ton frontend GitHub Pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK pour le dev / GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------
# Mapping symboles (frontend) -> tickers Yahoo
# --------------------------------------------
SYMBOLS = {
    "ES": {
        "yf": "ES=F",
        "label": "S&P 500 Futures",
    },
    "NQ": {
        "yf": "NQ=F",
        "label": "Nasdaq Futures",
    },
    "BTC": {
        "yf": "BTC-USD",
        "label": "Bitcoin / USD",
    },
    "CL": {
        "yf": "CL=F",
        "label": "Crude Oil (WTI)",
    },
    "GC": {
        "yf": "GC=F",
        "label": "Gold Futures",
    },
}

# Petit cache mémoire pour ne pas spammer Yahoo Finance
CACHE_TTL = 30  # secondes
_cache = {}     # { "ES": { "fetched_at": timestamp, "data": {...} } }


def build_comment(symbol: str, change_pct: float) -> str:
    """Génère un mini commentaire en français en fonction de la variation."""
    base_names = {
        "ES": "S&P 500",
        "NQ": "Nasdaq",
        "BTC": "Bitcoin",
        "CL": "le pétrole",
        "GC": "l'or",
    }
    name = base_names.get(symbol, symbol)

    if abs(change_pct) < 0.15:
        return f"{name} quasi stable"
    direction = "hausse" if change_pct > 0 else "baisse"

    if abs(change_pct) > 1.5:
        intensity = "forte "
    elif abs(change_pct) > 0.5:
        intensity = ""
    else:
        intensity = "légère "

    return f"{name} en {intensity}{direction}"


def fetch_symbol_data(symbol: str) -> dict:
    """Récupère les données réelles pour un symbole (avec cache simple)."""
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        raise ValueError(f"Symbole inconnu : {symbol}")

    now = time.time()

    # ----- Cache -----
    cached = _cache.get(symbol)
    if cached and (now - cached["fetched_at"] < CACHE_TTL):
        return cached["data"]

    cfg = SYMBOLS[symbol]
    ticker = yf.Ticker(cfg["yf"])

    # On prend les 2 dernières clôtures quotidiennes pour calculer la variation
    hist = ticker.history(period="2d", interval="1d")
    if hist.empty:
        raise ValueError("Aucune donnée retournée par Yahoo Finance.")

    last_close = float(hist["Close"].iloc[-1])

    if len(hist) >= 2:
        prev_close = float(hist["Close"].iloc[-2])
        change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
    else:
        prev_close = None
        change_pct = 0.0

    data = {
        "symbol": symbol,
        "yf_symbol": cfg["yf"],
        "label": cfg["label"],
        "price": last_close,
        "change_pct": change_pct,
        "timestamp": now,
        "prev_close": prev_close,
        "comment": build_comment(symbol, change_pct),
    }

    _cache[symbol] = {"fetched_at": now, "data": data}
    return data


# ==========================
# Endpoint de test
# ==========================
@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}


# ==========================
# Endpoint multi-actifs
# ==========================
@app.get("/latest")
async def latest(symbol: str = Query("ES")):
    """
    Renvoie les données du dernier prix pour un actif donné.
    Données réelles (retardées) via Yahoo Finance.
    """
    symbol = symbol.upper()

    if symbol not in SYMBOLS:
        return JSONResponse(
            {"error": f"Symbole inconnu : {symbol}"},
            status_code=404,
        )

    try:
        data = fetch_symbol_data(symbol)
        return JSONResponse(data)
    except Exception as e:
        # On évite que l'API crashe et on renvoie un JSON propre
        return JSONResponse(
            {"error": f"Erreur lors de la récupération des données : {str(e)}"},
            status_code=500,
        )
