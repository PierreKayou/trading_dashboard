# ============================================
#  trading_dashboard / api.py
#  API backend simple pour ton dashboard Trading
#  (données mockées pour l’instant)
# ============================================

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Création de l'application FastAPI
app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour récupérer les données de marché (mock pour l’instant)",
    version="1.0"
)

# CORS : autoriser ton frontend (GitHub Pages, localhost, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # pour le dev on autorise tout
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Endpoint racine : /  (test)
# -----------------------------
@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}


# -----------------------------
# Endpoint principal : /latest
# -----------------------------
@app.get("/latest")
async def latest(symbol: str = Query("ES")):
    """
    Renvoie les données mockées du dernier prix pour un actif donné.
    Pour l'instant, on simule juste le flux en attendant Rithmic.
    """

    fake_data = {
        "ES": {
            "price": 5290.25,
            "change_pct": +0.45,
            "comment": "S&P 500 calme avant l'ouverture",
        },
        "NQ": {
            "price": 18880.75,
            "change_pct": +0.62,
            "comment": "Nasdaq rebond technique",
        },
        "BTC": {
            "price": 102500,
            "change_pct": -0.95,
            "comment": "Bitcoin en phase de consolidation",
        },
        "CL": {
            "price": 78.10,
            "change_pct": +0.15,
            "comment": "Pétrole légèrement haussier",
        },
        "GC": {
            "price": 2320.00,
            "change_pct": -0.20,
            "comment": "Or en léger retracement",
        },
    }

    # Par sécurité, on met le symbole en majuscules
    symbol = symbol.upper()

    # On récupère les données mockées
    data = fake_data.get(symbol)

    if data is None:
        return JSONResponse(
            {"error": f"Aucune donnée disponible pour {symbol}"},
            status_code=404,
        )

    return JSONResponse(data)
