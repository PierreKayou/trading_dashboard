from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yfinance as yf

app = FastAPI(title="Trading Dashboard API")

# Autoriser GitHub Pages à appeler Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}

@app.get("/latest")
async def latest(symbol: str = Query("ES")):
    """
    Petite API simple : récupère les derniers prix via yfinance.
    Les données sont retournées en USD.
    """

    symbol = symbol.upper()
    yf_symbols = {
        "ES": "ES=F",
        "NQ": "NQ=F",
        "BTC": "BTC-USD",
        "CL": "CL=F",
        "GC": "GC=F",
    }

    if symbol not in yf_symbols:
        return JSONResponse({"error": f"Symbole invalide : {symbol}"}, status_code=400)

    try:
        ticker = yf.Ticker(yf_symbols[symbol])
        data = ticker.history(period="1d", interval="1m")

        if data.empty:
            return JSONResponse({"error": f"Aucune donnée pour {symbol}"}, status_code=404)

        last = data.iloc[-1]["Close"]
        prev = data.iloc[0]["Close"]
        change_pct = (last - prev) / prev * 100

        return {
            "symbol": symbol,
            "price": float(last),
            "change_pct": round(change_pct, 2),
            "comment": "OK"
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
