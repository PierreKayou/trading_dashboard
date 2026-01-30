# ============================================
#  trading_dashboard / api.py
#  Backend FastAPI : données marché + analyse IA
# ============================================

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import time
import json

import yfinance as yf
import pandas as pd
import numpy as np

from openai import OpenAI


# ==========================
# Config FastAPI
# ==========================

app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour récupérer les données de marché et les analyser avec un assistant OpenAI",
    version="1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # pour le dev, on ouvre tout
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# OpenAI – Assistant
# ==========================

client = OpenAI()
ASSISTANT_ID = "asst_yGo05VI8tVCJahE2vU911r1B"   # <- ton assistant Stark (change si besoin)


# ==========================
# Mapping symboles -> yfinance
# ==========================

SYMBOLS_CONFIG = {
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


# ==========================
# Utilitaires indicateurs
# ==========================

def compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def compute_macd(series: pd.Series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(hist.iloc[-1])


def build_comment(change_pct: float, rsi: float) -> str:
    """Petit commentaire automatique pour le dashboard."""
    if abs(change_pct) < 0.15:
        if 45 <= rsi <= 55:
            return "Marché quasi stable"
        elif rsi < 40:
            return "Légère pression vendeuse"
        else:
            return "Légère pression acheteuse"

    if change_pct >= 0.15:
        if rsi > 70:
            return "Hausse avec surachat potentiel"
        return "Hausse modérée"

    # change_pct négatif
    if rsi < 30:
        return "Baisse avec survente potentielle"
    return "Baisse modérée"


# ==========================
# Construction d'un snapshot pour 1 symbole
# ==========================

def build_snapshot(symbol: str) -> dict:
    symbol = symbol.upper()
    cfg = SYMBOLS_CONFIG.get(symbol)

    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Symbole inconnu : {symbol}")

    yf_symbol = cfg["yf_symbol"]
    label = cfg["label"]

    ticker = yf.Ticker(yf_symbol)

    # Intraday 5 jours, 5 minutes (un peu plus léger que 1m)
    data = ticker.history(period="5d", interval="5m")
    if data.empty or len(data) < 50:
        raise HTTPException(
            status_code=500,
            detail=f"Pas assez de données intraday pour {symbol} ({yf_symbol})",
        )

    close = data["Close"]
    volume = data["Volume"]

    # RSI
    rsi_value = compute_rsi(close, period=14)

    # MACD
    macd, signal, hist = compute_macd(close)

    # SMA20 + Bollinger
    sma20 = float(close.rolling(20).mean().iloc[-1])
    rolling_std = close.rolling(20).std()
    bollinger_high = float(sma20 + 2 * rolling_std.iloc[-1])
    bollinger_low = float(sma20 - 2 * rolling_std.iloc[-1])

    # Volume
    last_volume = int(volume.iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = last_volume / vol_ma20 if vol_ma20 > 0 else 0.0
    vol_spike = vol_ratio >= 2

    # Prix et variation
    last_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    change_pct = float((last_price - prev_price) / prev_price * 100)

    # Niveaux intraday (jour courant)
    last_ts = data.index[-1]
    today = last_ts.date()
    today_data = data[data.index.date == today]

    if not today_data.empty:
        intraday_open = float(today_data["Open"].iloc[0])
        intraday_high = float(today_data["High"].max())
        intraday_low = float(today_data["Low"].min())
    else:
        intraday_open = intraday_high = intraday_low = None

    # Niveaux daily (1 mois)
    daily = ticker.history(period="1mo", interval="1d")

    prev_day_high = prev_day_low = prev_day_close = None
    month_high = month_low = None

    if not daily.empty:
        month_high = float(daily["High"].max())
        month_low = float(daily["Low"].min())

        if len(daily) >= 2:
            prev = daily.iloc[-2]
            prev_day_high = float(prev["High"])
            prev_day_low = float(prev["Low"])
            prev_day_close = float(prev["Close"])

    comment = build_comment(change_pct, rsi_value)

    return {
        "symbol": symbol,
        "label": label,
        "yf_symbol": yf_symbol,
        "timestamp": time.time(),

        "price": last_price,
        "change_pct": change_pct,
        "comment": comment,

        "rsi": rsi_value,
        "volume": last_volume,
        "volume_ratio": vol_ratio,
        "volume_spike": vol_spike,
        "macd": macd,
        "signal": signal,
        "hist": hist,
        "sma20": sma20,
        "bollinger_high": bollinger_high,
        "bollinger_low": bollinger_low,

        "intraday_open": intraday_open,
        "intraday_high": intraday_high,
        "intraday_low": intraday_low,

        "prev_day_high": prev_day_high,
        "prev_day_low": prev_day_low,
        "prev_day_close": prev_day_close,
        "month_high": month_high,
        "month_low": month_low,
    }


# ==========================
# Endpoints
# ==========================

@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}


@app.get("/latest")
async def latest(symbol: str = Query("ES", description="ES, NQ, BTC, CL ou GC")):
    """
    Snapshot marché pour un symbole.
    Utilisé par ton dashboard pour les prix & indicateurs.
    """
    snapshot = build_snapshot(symbol)
    return JSONResponse(snapshot)


@app.get("/analyze")
async def analyze(symbol: str = Query("ES", description="ES, NQ, BTC, CL ou GC")):
    """
    Analyse du marché par l'assistant Stark pour un symbole donné.
    """
    try:
        snapshot = build_snapshot(symbol)
        market_json = json.dumps(snapshot, ensure_ascii=False)

        # 1) Créer un thread avec les données du marché
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": f"""
Voici les données de marché pour l'actif {symbol} (JSON) :

{market_json}

Les champs incluent les indicateurs (RSI, MACD, Bollinger, volume…)
et les niveaux de prix (intraday, daily, mensuel).

À partir de ces données et des PDF DELTA Trading attachés à l'assistant,
donne-moi une ANALYSE SYNTHÉTIQUE en 5 points pour l'actif {symbol} uniquement :

1) Résumé très court
2) Biais global (haussier / baissier / neutre) + justification
3) Scénario haussier probable (court terme)
4) Scénario baissier probable (court terme)
5) Niveau de confiance (0 à 100)

Réponds en français, sous forme de texte structuré.
                    """.strip()
                }
            ]
        )

        # 2) Lancer le run
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
        )

        # 3) Poll jusqu'à completion
        while run.status not in ("completed", "failed", "cancelled", "expired"):
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )

        if run.status != "completed":
            raise HTTPException(
                status_code=500,
                detail=f"Erreur assistant : {run.status}",
            )

        # 4) Récupérer la dernière réponse de l'assistant
        messages = client.beta.threads.messages.list(thread_id=thread.id)

        response_text = ""
        for msg in messages.data:
            if msg.role == "assistant":
                for part in msg.content:
                    if part.type == "text":
                        response_text += part.text.value

        if not response_text:
            response_text = "Aucune réponse générée par l'assistant."

        return {
            "symbol": symbol,
            "snapshot": snapshot,
            "analysis": response_text,
        }

    except HTTPException:
        # on relance tel quel les erreurs déjà formatées
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
