###############################
# IMPORTS
###############################
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import yfinance as yf
import json
import time
import numpy as np

from openai import OpenAI

# Router macro (backend analyse macro)
from macro.router import router as macro_router


###############################
# CONFIG GLOBALE
###############################
app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour ton Stark Trading Dashboard (yfinance + OpenAI + macro)",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # pour dev / GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# On branche le router macro sous /api
app.include_router(macro_router, prefix="/api")


# Mapping symbol ↔ yfinance
SYMBOLS = {
    "ES": {"label": "S&P 500 Future", "yf": "ES=F"},
    "NQ": {"label": "Nasdaq 100 Future", "yf": "NQ=F"},
    "BTC": {"label": "Bitcoin", "yf": "BTC-USD"},
    "CL": {"label": "Crude Oil (WTI)", "yf": "CL=F"},
    "GC": {"label": "Gold", "yf": "GC=F"},
}

###############################
# OPENAI CLIENT + ASSISTANT
###############################
# La clé est lue dans la variable d'environnement OPENAI_API_KEY sur Render
client = OpenAI()

# Ton assistant “Stark” déjà configuré avec les PDF Delta Trading
ASSISTANT_ID = "asst_yGo05VI8tVCJahE2vU911r1B"


###############################
# FONCTIONS UTILITAIRES
###############################
def _make_comment(change_pct: float, rsi: float) -> str:
    """
    Petit commentaire FR rapide en fonction de la variation et du RSI.
    """
    if np.isnan(change_pct):
        return "Données de variation indisponibles."

    if change_pct > 1.5:
        return "Fort momentum haussier"
    if change_pct > 0.5:
        return "Tendance haussière modérée"
    if change_pct > 0.1:
        return "Légère pression acheteuse"
    if change_pct < -1.5:
        return "Fort momentum baissier"
    if change_pct < -0.5:
        return "Pression vendeuse modérée"
    if change_pct < -0.1:
        return "Légère pression vendeuse"

    # zone neutre : on nuance avec le RSI
    if rsi < 35:
        return "Marché plutôt survendu"
    if rsi > 65:
        return "Marché plutôt suracheté"
    return "Marché globalement neutre"


def build_snapshot(symbol: str) -> dict:
    """
    Construit un snapshot détaillé pour un symbole (indicateurs + niveaux).
    Utilise des données intraday récentes via yfinance.
    """
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbole inconnu : {symbol}")

    cfg = SYMBOLS[symbol]
    yf_symbol = cfg["yf"]

    ticker = yf.Ticker(yf_symbol)

    # Données intraday (5 jours, 5 minutes pour limiter un peu)
    data = ticker.history(period="5d", interval="5m")
    if data.empty or len(data) < 50:
        raise HTTPException(
            status_code=500,
            detail=f"Pas assez de données pour {symbol} ({yf_symbol})",
        )

    close = data["Close"]
    volume = data["Volume"].fillna(0)

    # ---------- RSI 14 ----------
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    rsi_value = float(rsi_series.iloc[-1])

    # ---------- MACD (12/26/9) ----------
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    macd = float(macd_line.iloc[-1])
    signal = float(signal_line.iloc[-1])
    histo = float(hist.iloc[-1])

    # ---------- SMA20 + Bollinger ----------
    sma20 = float(close.rolling(20).mean().iloc[-1])
    rolling_std = close.rolling(20).std()
    bollinger_high = float(sma20 + 2 * rolling_std.iloc[-1])
    bollinger_low = float(sma20 - 2 * rolling_std.iloc[-1])

    # ---------- Volume ----------
    last_volume = float(volume.iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = last_volume / vol_ma20 if vol_ma20 > 0 else 0.0
    vol_spike = vol_ratio >= 2

    # ---------- Prix & variation ----------
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
        intraday_open = intraday_high = intraday_low = None

    # ---------- Niveaux journaliers (1 mois) ----------
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

    comment = _make_comment(change_pct, rsi_value)

    return {
        "symbol": symbol,
        "label": cfg["label"],
        "yf_symbol": yf_symbol,
        "timestamp": time.time(),
        "price": last_price,
        "change_pct": change_pct,
        "comment": comment,
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
        # Intraday
        "intraday_open": intraday_open,
        "intraday_high": intraday_high,
        "intraday_low": intraday_low,
        # Journaliers
        "prev_day_high": prev_day_high,
        "prev_day_low": prev_day_low,
        "prev_day_close": prev_day_close,
        "month_high": month_high,
        "month_low": month_low,
    }


def build_market_overview() -> dict:
    """
    Construit une vue synthétique du marché pour tous les actifs surveillés.
    (prix, variation, commentaire)
    """
    overview = {}
    for sym in SYMBOLS.keys():
        try:
            snap = build_snapshot(sym)
            overview[sym] = {
                "symbol": sym,
                "label": snap["label"],
                "price": snap["price"],
                "change_pct": snap["change_pct"],
                "comment": snap["comment"],
                "rsi": snap["rsi"],
            }
        except Exception:
            # On ignore les erreurs sur un actif pour ne pas casser l'analyse globale
            continue
    return overview


###############################
# ENDPOINTS
###############################
@app.get("/")
async def root():
    return {"message": "API Trading Dashboard OK"}


@app.get("/latest")
async def latest(symbol: str = Query("ES")):
    """
    Dernier snapshot pour un actif (utilisé par le dashboard pour les cartes).
    """
    try:
        snapshot = build_snapshot(symbol)
        return JSONResponse(snapshot)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyze")
async def analyze(symbol: str = Query("ES")):
    """
    Analyse IA "tout-en-un" pour un actif.
    """
    try:
        symbol = symbol.upper()
        if symbol not in SYMBOLS:
            raise HTTPException(status_code=400, detail=f"Symbole inconnu : {symbol}")

        snapshot = build_snapshot(symbol)
        market_overview = build_market_overview()

        snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        market_json = json.dumps(market_overview, ensure_ascii=False)

        label = snapshot["label"]

        user_prompt = f"""
Tu es un assistant d'analyse de marché pour un trader discrétionnaire.
Tu combines les données techniques (RSI, MACD, Bollinger, niveaux intraday / journaliers)
avec le contexte global du marché.

Voici les données DÉTAILLÉES pour l'actif sélectionné ({symbol} – {label}) au format JSON :

{snapshot_json}

Voici une VUE SYNTHÉTIQUE du reste du marché surveillé (ES, NQ, BTC, CL, GC) :

{market_json}

À partir de ces informations ET de ce que tu as appris dans les documents Delta Trading,
produis une analyse en français structurée comme suit (format Markdown) :

1) Analyse globale du marché
2) Analyse SWING
3) Plan de trade SWING (théorique, pas un conseil)
4) Analyse intraday
5) Plan de trade intraday (théorique, pas un conseil)
6) Synthèse & risques (rappel clair que ce n'est PAS un conseil en investissement)
"""

        thread = client.beta.threads.create(
            messages=[{"role": "user", "content": user_prompt}]
        )

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
        )

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

        messages = client.beta.threads.messages.list(thread_id=thread.id)

        analysis_text = ""
        for msg in messages.data:
            if msg.role == "assistant":
                for part in msg.content:
                    if part.type == "text":
                        analysis_text += part.text.value

        if not analysis_text:
            analysis_text = (
                "Aucune réponse générée par l'assistant. Vérifie la configuration."
            )

        return {
            "symbol": symbol,
            "snapshot": snapshot,
            "analysis": analysis_text,
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
