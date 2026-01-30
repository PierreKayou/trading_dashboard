# ============================================
#  trading_dashboard / api.py
#  Backend FastAPI pour Stark Trading Dashboard
#  - Multi-actifs (ES, NQ, BTC, CL, GC)
#  - Données temps quasi réel via yfinance
#  - Snapshot avec indicateurs techniques
# ============================================

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import yfinance as yf
import pandas as pd
import time


app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour le Stark Trading Dashboard",
    version="1.0",
)

# -------------------------------------------------------------------
# CORS (frontend local)
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # pour le dev local, on ouvre tout
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Mapping symboles dashboard -> yfinance
# -------------------------------------------------------------------
SYMBOL_MAP = {
    "ES": {
        "yf_symbol": "ES=F",
        "label": "E-mini S&P 500",
    },
    "NQ": {
        "yf_symbol": "NQ=F",
        "label": "E-mini Nasdaq 100",
    },
    "BTC": {
        "yf_symbol": "BTC-USD",
        "label": "Bitcoin / USD",
    },
    "CL": {
        "yf_symbol": "CL=F",
        "label": "Pétrole brut WTI",
    },
    "GC": {
        "yf_symbol": "GC=F",
        "label": "Or (Gold futures)",
    },
}


# -------------------------------------------------------------------
# Fonction utilitaire : calcul du snapshot pour un symbole
# -------------------------------------------------------------------
def build_snapshot(symbol: str) -> dict:
    symbol = symbol.upper()

    if symbol not in SYMBOL_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Symbole inconnu : {symbol}",
        )

    meta = SYMBOL_MAP[symbol]
    yf_symbol = meta["yf_symbol"]

    ticker = yf.Ticker(yf_symbol)

    # --------- Données intraday (5 jours / 1 min) ---------
    data = ticker.history(period="5d", interval="1m")
    if data.empty or len(data) < 30:
        raise HTTPException(
            status_code=500,
            detail=f"Pas assez de données intraday pour {yf_symbol}",
        )

    close = data["Close"]
    volume = data["Volume"]

    # ---------- RSI (14) ----------
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi_value = float(rsi_series.iloc[-1])

    # ---------- MACD (12 / 26 / 9) ----------
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    macd = float(macd_line.iloc[-1])
    signal = float(signal_line.iloc[-1])
    histo = float(hist.iloc[-1])

    # ---------- SMA 20 + Bollinger ----------
    sma20 = float(close.rolling(20).mean().iloc[-1])
    rolling_std = close.rolling(20).std()
    bollinger_high = float(sma20 + 2 * rolling_std.iloc[-1])
    bollinger_low = float(sma20 - 2 * rolling_std.iloc[-1])

    # ---------- Volume ----------
    last_volume = int(volume.iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = last_volume / vol_ma20 if vol_ma20 > 0 else 0.0
    vol_spike = bool(vol_ratio >= 2)

    # ---------- Prix / variation ----------
    last_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    change_pct = float((last_price - prev_price) / prev_price * 100)

    # ---------- Niveaux intraday (jour en cours) ----------
    last_ts = data.index[-1]
    today = last_ts.date()
    today_data = data[data.index.date == today]

    if not today_data.empty:
        intraday_open = float(today_data["Open"].iloc[0])
        intraday_high = float(today_data["High"].max())
        intraday_low = float(today_data["Low"].min())
    else:
        intraday_open = None
        intraday_high = None
        intraday_low = None

    # ---------- Niveaux 5 jours ----------
    five_day_high = float(data["High"].max())
    five_day_low = float(data["Low"].min())

    # ---------- Niveaux journaliers (1 mois) ----------
    daily = ticker.history(period="1mo", interval="1d")

    prev_day_high = None
    prev_day_low = None
    prev_day_close = None
    month_high = None
    month_low = None

    if not daily.empty:
        month_high = float(daily["High"].max())
        month_low = float(daily["Low"].min())

        if len(daily) >= 2:
            prev = daily.iloc[-2]
            prev_day_high = float(prev["High"])
            prev_day_low = float(prev["Low"])
            prev_day_close = float(prev["Close"])

    # ---------- Petit commentaire auto ----------
    if change_pct > 1.0:
        comment = "Marché plutôt haussier"
    elif change_pct < -1.0:
        comment = "Pression vendeuse sur le marché"
    else:
        comment = "Marché plutôt neutre"

    return {
        "symbol": symbol,
        "yf_symbol": yf_symbol,
        "label": meta["label"],
        "price": last_price,
        "change_pct": change_pct,
        "timestamp": time.time(),

        # Indicateurs
        "rsi": rsi_value,
        "volume": last_volume,
        "volume_ratio": vol_ratio,
        "volume_spike": vol_spike,
        "macd": macd,
        "signal": signal,
        "hist": histo,
        "sma20": sma20,
        "bollinger_high": bollinger_high,
        "bollinger_low": bollinger_low,

        # Niveaux intraday
        "intraday_open": intraday_open,
        "intraday_high": intraday_high,
        "intraday_low": intraday_low,

        # 5 derniers jours
        "five_day_high": five_day_high,
        "five_day_low": five_day_low,

        # Journalier (1 mois)
        "prev_day_high": prev_day_high,
        "prev_day_low": prev_day_low,
        "prev_day_close": prev_day_close,
        "month_high": month_high,
        "month_low": month_low,

        "comment": comment,
    }


# -------------------------------------------------------------------
# Endpoint racine
# -------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}


# -------------------------------------------------------------------
# Endpoint principal : /latest?symbol=ES
# -------------------------------------------------------------------
@app.get("/latest")
async def latest(symbol: str = Query("ES")):
    """
    Renvoie un snapshot complet pour un symbole :
    ES, NQ, BTC, CL, GC
    """
    snapshot = build_snapshot(symbol)
    return JSONResponse(snapshot)
