###############################
# IMPORTS
###############################
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from datetime import datetime

import yfinance as yf
import json
import time
import numpy as np
import os

from openai import OpenAI

# Router macro (backend analyse macro)
from macro.router import router as macro_router

# : router news
from news.router import router as news_router

###############################
# CONFIG GLOBALE
###############################
app = FastAPI(
    title="Trading Dashboard API",
    description="Backend pour ton Stark Trading Dashboard (yfinance + OpenAI + macro)",
    version="1.2.0",
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
# On branche le router news sous /api
app.include_router(news_router, prefix="/api")


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
client = OpenAI()
ASSISTANT_ID = "asst_yGo05VI8tVCJahE2vU911r1B"


###############################
# FONCTIONS UTILITAIRES
###############################
def _make_comment(change_pct: float, rsi: float) -> str:
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

    if rsi < 35:
        return "Marché plutôt survendu"
    if rsi > 65:
        return "Marché plutôt suracheté"
    return "Marché globalement neutre"


def build_snapshot(symbol: str) -> dict:
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbole inconnu : {symbol}")

    cfg = SYMBOLS[symbol]
    yf_symbol = cfg["yf"]

    ticker = yf.Ticker(yf_symbol)

    data = ticker.history(period="5d", interval="5m")
    if data.empty or len(data) < 50:
        raise HTTPException(
            status_code=500,
            detail=f"Pas assez de données pour {symbol} ({yf_symbol})",
        )

    close = data["Close"]
    volume = data["Volume"].fillna(0)

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    rsi_value = float(rsi_series.iloc[-1])

    # MACD (12/26/9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    macd = float(macd_line.iloc[-1])
    signal = float(signal_line.iloc[-1])
    histo = float(hist.iloc[-1])

    # SMA20 + Bollinger
    sma20 = float(close.rolling(20).mean().iloc[-1])
    rolling_std = close.rolling(20).std()
    bollinger_high = float(sma20 + 2 * rolling_std.iloc[-1])
    bollinger_low = float(sma20 - 2 * rolling_std.iloc[-1])

    # Volume
    last_volume = float(volume.iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = last_volume / vol_ma20 if vol_ma20 > 0 else 0.0
    vol_spike = vol_ratio >= 2

    # Prix & variation
    last_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    change_pct = float((last_price - prev_price) / prev_price * 100)

    # Intraday (jour en cours)
    last_ts = data.index[-1]
    today = last_ts.date()
    today_data = data[data.index.date == today]

    if not today_data.empty:
        intraday_open = float(today_data["Open"].iloc[0])
        intraday_high = float(today_data["High"].max())
        intraday_low = float(today_data["Low"].min())
    else:
        intraday_open = intraday_high = intraday_low = None

    # Journaliers (1 mois)
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
        "intraday_open": intraday_open,
        "intraday_high": intraday_high,
        "intraday_low": intraday_low,
        "prev_day_high": prev_day_high,
        "prev_day_low": prev_day_low,
        "prev_day_close": prev_day_close,
        "month_high": month_high,
        "month_low": month_low,
    }


def build_market_overview() -> dict:
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
            continue
    return overview

def build_perf_summary() -> dict:
    """
    Calcule les performances journalières, hebdo et mensuelles
    pour chaque indice de SYMBOLS en %.
    J = dernier close vs veille
    W = dernier close vs ~5 séances avant
    M = dernier close vs ~21 séances avant
    """
    assets = []
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    for sym, cfg in SYMBOLS.items():
        yf_symbol = cfg["yf"]
        ticker = yf.Ticker(yf_symbol)

        # On prend un peu de recul pour avoir les 21 séances
        hist = ticker.history(period="2mo", interval="1d")
        if hist.empty or len(hist) < 3:
            # Pas assez de données
            assets.append(
                {
                    "symbol": sym,
                    "label": cfg["label"],
                    "d": None,
                    "w": None,
                    "m": None,
                }
            )
            continue

        closes = hist["Close"].dropna()
        if len(closes) < 3:
            assets.append(
                {
                    "symbol": sym,
                    "label": cfg["label"],
                    "d": None,
                    "w": None,
                    "m": None,
                }
            )
            continue

        last = float(closes.iloc[-1])

        # Jour = dernier vs veille
        if len(closes) >= 2:
            prev_day = float(closes.iloc[-2])
            d = (last - prev_day) / prev_day * 100 if prev_day != 0 else None
        else:
            d = None

        # Semaine = ~5 séances avant
        if len(closes) >= 6:
            prev_week = float(closes.iloc[-6])
            w = (last - prev_week) / prev_week * 100 if prev_week != 0 else None
        else:
            w = None

        # Mois = ~21 séances avant
        if len(closes) >= 22:
            prev_month = float(closes.iloc[-22])
            m = (last - prev_month) / prev_month * 100 if prev_month != 0 else None
        else:
            m = None

        assets.append(
            {
                "symbol": sym,
                "label": cfg["label"],
                "d": d,
                "w": w,
                "m": m,
            }
        )

    return {
        "as_of": today_str,
        "assets": assets,
    }

def get_macro_state() -> dict:
    """
    Récupère l'état macro hebdo.

    Version simple :
    - Essaie de lire un fichier 'macro_state.json' (éventuellement écrit par le router macro)
    - Sinon, renvoie un régime neutre par défaut

    Tu pourras remplacer cette logique par un import direct depuis macro.router
    si tu exposes une fonction Python côté macro.
    """
    try:
        file_path = os.path.join(os.getcwd(), "macro_state.json")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass

    # Fallback : macro neutre
    return {
        "timestamp": None,
        "macro_regime": {
            "label": "Neutre",
            "confidence": 0.5,
            "stability": "stable",
        },
        "macro_factors": {
            "monetary_policy": "neutre",
            "inflation_trend": "stable",
            "growth_trend": "stable",
            "risk_sentiment": "neutre",
            "rates_pressure": "neutre",
            "usd_bias": "neutre",
        },
        "market_bias": {
            "equities": "contexte neutre",
            "indices_us": "contexte neutre",
            "commodities": "contexte neutre",
            "crypto": "contexte neutre",
        },
        "invalidations": [],
        "commentary": "Aucun contexte macro explicite disponible, régime neutre par défaut.",
    }


###############################
# ENDPOINTS
###############################
@app.get("/health")
async def health():
    # Petit ping JSON si besoin
    return {"message": "API Trading Dashboard OK"}


@app.get("/latest")
async def latest(symbol: str = Query("ES")):
    try:
        snapshot = build_snapshot(symbol)
        return JSONResponse(snapshot)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/perf/summary")
async def perf_summary():
    """
    Tableau récapitulatif des performances J / W / M pour les indices suivis.
    """
    try:
        summary = build_perf_summary()
        return JSONResponse(summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyze")
async def analyze(symbol: str = Query("ES")):
    """
    Analyse IA d'un actif en tenant compte :
    - du snapshot technique
    - de la vue globale marché
    - du contexte macro hebdo (macro_state)
    """
    try:
        symbol = symbol.upper()
        if symbol not in SYMBOLS:
            raise HTTPException(status_code=400, detail=f"Symbole inconnu : {symbol}")

        # 1) Données marché
        snapshot = build_snapshot(symbol)
        market_overview = build_market_overview()
        macro_state = get_macro_state()

        snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        market_json = json.dumps(market_overview, ensure_ascii=False)
        macro_json = json.dumps(macro_state, ensure_ascii=False)

        label = snapshot["label"]

        user_prompt = f"""
Tu es un assistant d'analyse de marché pour un trader discrétionnaire dans le cadre du projet Trading Dash.

Tu dois combiner :
- le CONTEXTE MACRO hebdomadaire,
- les données techniques détaillées de l'actif analysé,
- et la vue d'ensemble du reste du marché,

pour produire une analyse structurée, lisible dans un dashboard.

Voici le CONTEXTE MACRO HEBDOMADAIRE GLOBAL au format JSON :
{macro_json}

Voici les données DÉTAILLÉES pour l'actif sélectionné ({symbol} – {label}) au format JSON :
{snapshot_json}

Voici une VUE SYNTHÉTIQUE du reste du marché surveillé (ES, NQ, BTC, CL, GC) :
{market_json}

OBJECTIF :
Produire une analyse en français, orientée trader discrétionnaire, qui :
- respecte le contexte macro (tu indiques si l'actif est « aligné » ou « à contre-courant » du régime macro),
- reste descriptive et probabiliste (PAS de certitudes ni de signaux d'entrée bruts),
- met en avant les niveaux/structures importants plutôt que des prévisions de prix.

STRUCTURE ATTENDUE (markdown simple) :

1. **Contexte macro et climat de marché**
   - Résume en 3–5 phrases le régime macro dominant (risk-on / risk-off / neutre, dollar, taux, sentiment).
   - Explique en quoi ce contexte est globalement favorable ou défavorable aux actifs risqués.

2. **Lecture de l'actif : {symbol} – {label}**
   - Tendances principales (intraday / daily) : haussière, baissière, range, transition.
   - Indicateurs techniques clés (RSI, MACD, Bollinger, volumes, niveaux intraday/journaliers) : ce qu'ils suggèrent.
   - Niveaux de prix importants : supports, résistances, zones de liquidité / intérêt.

3. **Cohérence avec le contexte macro**
   - Indique si le comportement actuel de {symbol} est :
     - « cohérent avec le régime macro »,
     - « en décalage / contre le régime macro »,
     - ou « neutre / peu sensible au macro ».
   - Explique brièvement pourquoi (corrélation typique, profil de risque, etc.).

4. **Scénarios et zones à surveiller (PAS de signaux de trade)**
   - Scénario haussier : quelles conditions techniques pourraient le valider ? quels niveaux clés ?
   - Scénario baissier : idem.
   - Points d'attention : volatilité, news sensibles, zones où le trader doit être particulièrement prudent.
   - Toujours formuler en termes de « si… alors… », jamais en certitude.

5. **Synthèse ultra-courte pour le dashboard**
   - 2 phrases maximum qui résument :
     - le climat macro,
     - le biais probable / prudence sur {symbol}.

RÈGLES :
- Ne propose PAS d’ordres concrets (pas de « achète », « vends », « stop à », « TP à »).
- Ne donne PAS de taille de position, pas de levier.
- Ne prétends PAS connaître l’avenir : tu décris des contextes, des probabilités, des structures.
- Si les données sont contradictoires ou confuses, tu le dis clairement : le doute fait partie de l'analyse.
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
            "macro": macro_state,
            "analysis": analysis_text,
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root_page():
    """
    Sert la page principale par défaut (alias de index.html).
    """
    file_path = os.path.join(os.getcwd(), "index.html")
    return FileResponse(file_path)


@app.get("/index.html")
async def index_page():
    """
    Sert la page principale du dashboard trading.
    """
    file_path = os.path.join(os.getcwd(), "index.html")
    return FileResponse(file_path)


@app.get("/macro.html")
async def macro_page():
    """
    Sert la page front de la vue macro hebdomadaire.
    """
    file_path = os.path.join(os.getcwd(), "macro.html")
    return FileResponse(file_path)
