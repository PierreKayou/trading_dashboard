from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
import yfinance as yf
import time

app = FastAPI()

# ------------------------------------------------------------
# Instruments supportés
# ------------------------------------------------------------
INSTRUMENTS = {
    "ES":  {"yf_symbol": "ES=F",  "label": "S&P 500 Future"},
    "NQ":  {"yf_symbol": "NQ=F",  "label": "Nasdaq Future"},
    "BTC": {"yf_symbol": "BTC-USD", "label": "Bitcoin"},
    "CL":  {"yf_symbol": "CL=F",  "label": "Crude Oil (WTI)"},
    "GC":  {"yf_symbol": "GC=F",  "label": "Gold"},
}

# ------------------------------------------------------------
# Fonction utilitaire : récupérer le dernier prix + précédent
# ------------------------------------------------------------
def get_last_prices(symbol: str):
    """
    Retourne (last_price, previous_close)
    """
    data = yf.download(symbol, period="2d", interval="1d")

    if data is None or data.empty:
        raise ValueError(f"Impossible de récupérer les données pour {symbol}")

    last_row = data.iloc[-1]
    prev_row = data.iloc[-2] if len(data) > 1 else None

    last_price = float(last_row["Close"])
    prev_price = float(prev_row["Close"]) if prev_row is not None else None

    return last_price, prev_price


# ------------------------------------------------------------
# Génération d’un commentaire simple selon la variation %
# ------------------------------------------------------------
def build_comment(symbol: str, label: str, pct: float) -> str:
    if pct > 0.4:
        return f"{label} nettement haussier"
    if pct > 0.15:
        return f"{label} en légère hausse"
    if pct > -0.15:
        return f"{label} quasi stable"
    if pct > -0.4:
        return f"{label} en légère baisse"
    return f"{label} en forte baisse"


# ------------------------------------------------------------
# Endpoint racine
# ------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}


# ------------------------------------------------------------
# Endpoint principal /latest
# ------------------------------------------------------------
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur backend : {e}")

    # Variation %
    if prev_price and prev_price != 0:
        change_pct = (last_price - prev_price) / prev_price * 100.0
    else:
        change_pct = 0.0

    comment = build_comment(symbol, label, change_pct)

    # --------------------------------------------------------
    # 🔥 IMPORTANT :
    # Compatibilité totale avec ton frontend actuel :
    # -> ton HTML attend "price", pas "price_usd"
    # --------------------------------------------------------
    payload = {
        "symbol": symbol,
        "yf_symbol": yf_symbol,
        "label": label,

        # Champ utilisé par le frontend 🌟
        "price": round(last_price, 2),

        # Champ pour ton futur bouton USD/EUR
        "price_usd": round(last_price, 2),

        "change_pct": round(change_pct, 2),
        "timestamp": time.time(),
        "comment": comment,
    }

    return JSONResponse(payload)
