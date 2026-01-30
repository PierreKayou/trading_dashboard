# ============================================
#  trading_dashboard / api.py
#  API backend simple pour ton dashboard
# ============================================

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour récupérer les données de marché (mockées)",
    version="1.0",
)

# CORS : on laisse le front (GitHub Pages) interroger l'API Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok pour dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    Renvoie des prix mockés en **USD** pour un actif donné.
    Le front se charge de convertir en EUR si besoin.
    """

    fake_data = {
        "ES": {
            "symbol": "ES",
            "name": "S&P 500 Future",
            "price": 5290.25,
            "change_pct": 0.45,
            "comment": "S&P 500 calme avant l'ouverture",
        },
        "NQ": {
            "symbol": "NQ",
            "name": "Nasdaq 100 Future",
            "price": 18880.75,
            "change_pct": 0.62,
            "comment": "Nasdaq rebond technique",
        },
        "BTC": {
            "symbol": "BTC",
            "name": "Bitcoin",
            "price": 102500.00,
            "change_pct": -0.95,
            "comment": "Bitcoin en phase de consolidation",
        },
        "CL": {
            "symbol": "CL",
            "name": "Crude Oil (WTI)",
            "price": 78.10,
            "change_pct": 0.15,
            "comment": "Pétrole légèrement haussier",
        },
        "GC": {
            "symbol": "GC",
            "name": "Gold",
            "price": 2320.00,
            "change_pct": -0.20,
            "comment": "Or en léger retracement",
        },
    }

    # symbole en majuscules par sécurité
    symbol = symbol.upper()

    data = fake_data.get(symbol)
    if data is None:
        return JSONResponse(
            {"error": f"Aucune donnée disponible pour {symbol}"},
            status_code=404,
        )

    return JSONResponse(data)
