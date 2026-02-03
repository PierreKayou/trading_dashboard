# macro/router.py

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import datetime as dt
import time
import os

import yfinance as yf
import numpy as np

from news.router import fetch_raw_news  # on réutilise ton agrégateur de news

router = APIRouter(prefix="/api/macro", tags=["macro"])

# Univers suivi (mêmes tickers que sur l'index)
SYMBOLS: Dict[str, Dict[str, str]] = {
    "ES": {"name": "S&P 500 Future", "yf": "ES=F"},
    "NQ": {"name": "Nasdaq 100 Future", "yf": "NQ=F"},
    "BTC": {"name": "Bitcoin", "yf": "BTC-USD"},
    "CL": {"name": "Crude Oil (WTI)", "yf": "CL=F"},
    "GC": {"name": "Gold", "yf": "GC=F"},
}

BUCKETS = ["macro_us", "macro_europe", "companies", "geopolitics", "tech"]


# ---------------------------------------------------------------------------
# Outils de base : bornes de semaine + perfs
# ---------------------------------------------------------------------------

def _get_week_bounds(today: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """
    Retourne (lundi, dimanche) de la semaine courante.
    """
    if today is None:
        today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday())
    end = start + dt.timedelta(days=6)
    return start, end


def _compute_weekly_performances(start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
    """
    Calcule la perf % de chaque actif entre le premier cours de la semaine
    (ou le plus proche disponible) et le dernier cours dispo.
    """
    assets: List[Dict[str, Any]] = []

    for sym, cfg in SYMBOLS.items():
        yf_symbol = cfg["yf"]
        name = cfg["name"]

        try:
            # On prend un peu large pour être sûr d'avoir le début de semaine
            hist = yf.Ticker(yf_symbol).history(period="1mo", interval="1d")
        except Exception:
            continue

        if hist.empty or "Close" not in hist.columns:
            continue

        closes = hist["Close"].dropna()
        if closes.empty:
            continue

        # Date du dernier close
        last_close = float(closes.iloc[-1])

        # On cherche le premier cours >= début de semaine,
        # sinon on prend le premier close dispo (fallback).
        idx_week = [i for i, ts in enumerate(closes.index) if ts.date() >= start]
        if idx_week:
            base_close = float(closes.iloc[idx_week[0]])
        else:
            base_close = float(closes.iloc[0])

        if base_close == 0:
            ret_pct = 0.0
        else:
            ret_pct = (last_close - base_close) / base_close * 100.0

        assets.append(
            {
                "symbol": sym,
                "name": name,
                "return_pct": ret_pct,
            }
        )

    return assets


# ---------------------------------------------------------------------------
# Sentiment news : classification & scoring
# ---------------------------------------------------------------------------

def _classify_bucket(title: str) -> str:
    """
    Classe grossièrement une news dans un bucket thématique :
    macro_us, macro_europe, companies, geopolitics, tech.
    """
    t = (title or "").lower()

    if any(k in t for k in ["fed", "treasury", "cpi", "inflation", "payroll",
                            "jobs report", "unemployment", "gdp", "fomc"]):
        return "macro_us"

    if any(k in t for k in ["ecb", "eurozone", "euro zone", "european central bank",
                            "europe", "euro area", "uk ", "germany", "france",
                            "italy", "spain"]):
        return "macro_europe"

    if any(k in t for k in ["war", "conflict", "tension", "sanction", "geopolitic",
                            "middle east", "ukraine", "russia", "gaza", "israel",
                            "taiwan", "border"]):
        return "geopolitics"

    if any(k in t for k in ["ai", "artificial intelligence", "chip", "semiconductor",
                            "nvidia", "amd", "intel", "microsoft", "google",
                            "alphabet", "apple", "meta", "amazon", "cloud",
                            "software", "technology", "tech "]):
        return "tech"

    # Par défaut, on considère que c'est plutôt "entreprises"
    return "companies"


def _score_sentiment(text: str) -> float:
    """
    Score très simple en [-1, +1] basé sur quelques mots positifs/négatifs
    dans le titre (ou le titre + description si tu rajoutes plus tard).
    """
    t = (text or "").lower()

    positives = [
        "rally", "surge", "jump", "soar", "record", "beat", "beats",
        "strong", "growth", "better than", "optimism", "optimistic",
        "upgrade", "bull", "bullish", "rebound", "recovery",
    ]
    negatives = [
        "selloff", "sell-off", "plunge", "drop", "fall", "tumble", "slump",
        "crash", "fear", "fears", "concern", "concerns", "warning",
        "profit warning", "cut", "cuts", "downgrade", "bear", "bearish",
        "recession", "slowdown",
    ]

    pos = sum(1 for w in positives if w in t)
    neg = sum(1 for w in negatives if w in t)

    if pos == 0 and neg == 0:
        return 0.0

    return float((pos - neg) / (pos + neg))


def _build_sentiment_grid(start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
    """
    Construit la grille:
    [
      { date, bucket, sentiment, news_count },
      ...
    ]
    en utilisant fetch_raw_news (yfinance + NewsAPI).
    """
    try:
        raw = fetch_raw_news(max_articles=200)
    except Exception:
        raw = {"articles": []}

    articles = raw.get("articles", []) or []
    daily: Dict[str, Dict[str, Dict[str, float]]] = {}

    for art in articles:
        title = art.get("title") or ""
        if not title.strip():
            continue

        ts = art.get("providerPublishTime")
        if not ts:
            # si pas de timestamp, on ignore pour la grille hebdo
            continue

        try:
            dt_obj = dt.datetime.utcfromtimestamp(ts)
        except Exception:
            continue

        day = dt_obj.date()
        if day < start or day > end:
            continue

        bucket = _classify_bucket(title)
        score = _score_sentiment(title)

        day_str = day.isoformat()
        if day_str not in daily:
            daily[day_str] = {b: {"sum": 0.0, "count": 0} for b in BUCKETS}

        bucket_data = daily[day_str][bucket]
        bucket_data["sum"] += score
        bucket_data["count"] += 1

    # On génère la grille en remplissant tous les jours / buckets,
    # même quand il n'y a pas eu de news (news_count = 0).
    grid: List[Dict[str, Any]] = []
    one_day = dt.timedelta(days=1)
    d = start
    while d <= end:
        day_str = d.isoformat()
        stats_for_day = daily.get(
            day_str,
            {b: {"sum": 0.0, "count": 0} for b in BUCKETS},
        )

        for bucket in BUCKETS:
            data = stats_for_day.get(bucket, {"sum": 0.0, "count": 0})
            count = int(data["count"])
            avg = float(data["sum"] / count) if count > 0 else 0.0

            grid.append(
                {
                    "date": day_str,
                    "bucket": bucket,
                    "sentiment": avg,
                    "news_count": count,
                }
            )
        d += one_day

    return grid


# ---------------------------------------------------------------------------
# Heuristiques globales de "risk-on / risk-off"
# ---------------------------------------------------------------------------

def _compute_risk_profile(asset_perfs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Traduit les perfs de la semaine en un biais macro simple.
    """
    rets = np.array([a["return_pct"] for a in asset_perfs if a.get("return_pct") is not None])
    if rets.size == 0:
        return {
            "risk_on": None,
            "label": "Lecture macro neutre",
            "comment": "Données insuffisantes pour déterminer un biais macro.",
        }

    avg = float(np.mean(rets))

    if avg > 1.0:
        return {
            "risk_on": True,
            "label": "Biais macro global : risk-on",
            "comment": (
                "Biais plutôt risk-on : les actifs risqués s'inscrivent globalement "
                "en hausse cette semaine, dans un contexte plus favorable au risque."
            ),
        }
    elif avg < -1.0:
        return {
            "risk_on": False,
            "label": "Biais macro global : risk-off",
            "comment": (
                "Biais plutôt risk-off : la majorité des actifs sont sous pression "
                "cette semaine, avec un contexte plus défensif sur les marchés."
            ),
        }
    else:
        return {
            "risk_on": False,
            "label": "Biais macro global : neutre / mitigé",
            "comment": (
                "Lecture macro mitigée : les performances hebdomadaires des actifs "
                "sont mélangées, sans biais clair en faveur du risk-on ou du risk-off."
            ),
        }


def _compute_macro_bias_assets(asset_perfs: List[Dict[str, Any]],
                               risk_on: bool | None) -> List[Dict[str, Any]]:
    """
    Associe à chaque actif un biais macro très simple (bullish / bearish / neutral)
    en fonction de sa perf relative et du climat global.
    """
    if not asset_perfs:
        return []

    rets = np.array([a["return_pct"] for a in asset_perfs])
    mean = float(np.mean(rets))
    std = float(np.std(rets)) if rets.size > 1 else 0.0

    assets_with_bias: List[Dict[str, Any]] = []
    for a in asset_perfs:
        r = a["return_pct"]
        if std > 0:
            z = (r - mean) / std
        else:
            z = 0.0

        # seuils très simples
        if z > 0.5:
            bias = "bullish"
        elif z < -0.5:
            bias = "bearish"
        else:
            bias = "neutral"

        # On renvoie juste "macro_bias" pour ton index
        assets_with_bias.append(
            {
                "symbol": a["symbol"],
                "name": a["name"],
                "return_pct": r,
                "macro_bias": bias,
            }
        )

    return assets_with_bias


def _build_top_moves(asset_perfs: List[Dict[str, Any]],
                     max_moves: int = 3) -> List[Dict[str, Any]]:
    """
    Sélectionne les mouvements les plus marquants de la semaine
    pour la carte "MOUVEMENTS MARQUANTS".
    """
    if not asset_perfs:
        return []

    # tri absolu décroissant
    ordered = sorted(asset_perfs, key=lambda a: abs(a["return_pct"]), reverse=True)
    top = ordered[:max_moves]

    moves: List[Dict[str, Any]] = []
    for a in top:
        sym = a["symbol"]
        name = a["name"]
        r = a["return_pct"]
        sign = "+" if r > 0 else ""
        description = f"{sym} ({name}) en {'hausse' if r >= 0 else 'baisse'} de {sign}{r:.2f} % sur la semaine."

        moves.append(
            {
                "asset": sym,
                "move_pct": r,
                "description": description,
            }
        )

    return moves


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("/week/summary")
def get_week_summary() -> Dict[str, Any]:
    """
    Vue synthétique pour la page macro :
    - start / end : bornes de la semaine
    - risk_on / risk_comment : climat global
    - top_events : (placeholder pour l'instant)
    - top_moves : mouvements marquants de la semaine
    """
    start, end = _get_week_bounds()
    asset_perfs = _compute_weekly_performances(start, end)
    risk_profile = _compute_risk_profile(asset_perfs)

    summary = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "created_at": time.time(),
        "risk_on": risk_profile["risk_on"],
        "risk_comment": risk_profile["comment"],
        "top_events": [],  # on remplira ça à l'étape C
        "top_moves": _build_top_moves(asset_perfs),
    }
    return summary


@router.get("/week/raw")
def get_week_raw() -> Dict[str, Any]:
    """
    Données détaillées pour la page macro :
    - asset_performances : [{symbol, name, return_pct}]
    - sentiment_grid : [{date, bucket, sentiment, news_count}]
    """
    start, end = _get_week_bounds()
    asset_perfs = _compute_weekly_performances(start, end)
    grid = _build_sentiment_grid(start, end)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "created_at": time.time(),
        "asset_performances": asset_perfs,
        "sentiment_grid": grid,
    }


@router.get("/bias")
def get_bias() -> Dict[str, Any]:
    """
    Biais macro par actif (utilisé par l'index pour les petites lignes
    'Biais macro haussier / baissier / neutre').
    """
    start, end = _get_week_bounds()
    asset_perfs = _compute_weekly_performances(start, end)
    risk_profile = _compute_risk_profile(asset_perfs)

    assets_with_bias = _compute_macro_bias_assets(
        asset_perfs,
        risk_on=risk_profile["risk_on"],
    )

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "created_at": time.time(),
        "risk_on": risk_profile["risk_on"],
        "label": risk_profile["label"],
        "comment": risk_profile["comment"],
        "assets": assets_with_bias,
    }
