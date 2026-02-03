# macro/router.py

from fastapi import APIRouter, HTTPException
import datetime as dt
import time
from typing import List, Dict, Any

import yfinance as yf

router = APIRouter(prefix="/api/macro", tags=["macro"])

# Les mêmes grands actifs que le reste du dash
ASSETS = [
    {"symbol": "ES", "name": "S&P 500 Future", "yf": "ES=F"},
    {"symbol": "NQ", "name": "Nasdaq 100 Future", "yf": "NQ=F"},
    {"symbol": "BTC", "name": "Bitcoin", "yf": "BTC-USD"},
    {"symbol": "CL", "name": "Crude Oil (WTI)", "yf": "CL=F"},
    {"symbol": "GC", "name": "Gold", "yf": "GC=F"},
]


# -------------------------------
# FONCTIONS UTILITAIRES
# -------------------------------

def _current_week_range() -> tuple[dt.date, dt.date]:
    """
    Retourne (start, end) de la semaine courante :
    - start = lundi
    - end   = dimanche
    """
    today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday())  # lundi
    end = start + dt.timedelta(days=6)                  # dimanche
    return start, end


def _compute_weekly_returns() -> List[Dict[str, Any]]:
    """
    Pour chaque actif, calcule la perf hebdo approximative :
    - on prend les closes des 7 derniers jours
    - perf = dernier close / premier close - 1
    """
    results: List[Dict[str, Any]] = []

    for a in ASSETS:
        sym = a["symbol"]
        yf_sym = a["yf"]

        try:
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period="7d", interval="1d")
        except Exception as e:
            results.append(
                {
                    "symbol": sym,
                    "name": a["name"],
                    "return_pct": None,
                    "error": str(e),
                }
            )
            continue

        if hist.empty or "Close" not in hist.columns:
            results.append(
                {
                    "symbol": sym,
                    "name": a["name"],
                    "return_pct": None,
                    "error": "No data",
                }
            )
            continue

        closes = hist["Close"].dropna()
        if len(closes) < 2:
            results.append(
                {
                    "symbol": sym,
                    "name": a["name"],
                    "return_pct": None,
                    "error": "Not enough data",
                }
            )
            continue

        first = float(closes.iloc[0])
        last = float(closes.iloc[-1])

        if first == 0:
            ret = None
        else:
            ret = (last - first) / first * 100.0

        results.append(
            {
                "symbol": sym,
                "name": a["name"],
                "return_pct": ret,
            }
        )

    return results


def _infer_risk_bias(asset_perfs: List[Dict[str, Any]]) -> tuple[bool | None, str]:
    """
    À partir des perfs hebdo, on déduit un biais global simple :
    - moyenne > +0.5%  -> risk-on
    - moyenne < -0.5%  -> risk-off
    - sinon            -> neutre
    Retourne (risk_on, commentaire)
    """
    vals = [
        a["return_pct"]
        for a in asset_perfs
        if a.get("return_pct") is not None
    ]

    if not vals:
        return None, (
            "Lecture neutre : impossible de calculer les performances hebdomadaires "
            "des actifs suivis (données insuffisantes)."
        )

    avg = sum(vals) / len(vals)

    if avg > 0.5:
        return True, (
            "Biais plutôt risk-on : la majorité des actifs terminent la semaine en hausse, "
            "ce qui reflète un appétit modéré pour le risque."
        )

    if avg < -0.5:
        return False, (
            "Biais plutôt risk-off : la majorité des actifs sont sous pression cette semaine, "
            "avec un contexte plus défensif sur les marchés."
        )

    return None, (
        "Lecture neutre : les performances hebdomadaires des indices et de l'or sont mitigées ; "
        "le marché ne donne pas de signal clair d'appétit pour le risque ou de défiance."
    )


def _build_dummy_sentiment_grid(start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
    """
    Grille de sentiment très simple (neutre partout) pour alimenter la vue.
    On remplira avec de vraies données plus tard.
    """
    buckets = ["macro_us", "macro_europe", "companies", "geopolitics", "tech"]
    cells: List[Dict[str, Any]] = []

    d = start
    while d <= end:
        if d.weekday() < 5:  # 0 = lundi, ..., 4 = vendredi
            for b in buckets:
                cells.append(
                    {
                        "date": d.isoformat(),
                        "bucket": b,
                        "sentiment": 0.0,   # neutre
                        "news_count": 0,    # pas encore de comptage réel
                    }
                )
        d += dt.timedelta(days=1)

    return cells


def _risk_label_from_flag(flag: bool | None) -> str:
    """
    Texte court pour la bannière du dash.
    """
    if flag is True:
        return "Biais macro global : risk-on"
    if flag is False:
        return "Biais macro global : risk-off"
    return "Biais macro global : neutre"


# -------------------------------
# ENDPOINTS
# -------------------------------

@router.get("/week/summary")
async def get_week_summary():
    """
    Vue synthétique pour la page macro :
    - start / end
    - risk_on / risk_comment
    - top_events / top_moves (placeholder pour l'instant)
    """
    try:
        start, end = _current_week_range()
        perfs = _compute_weekly_returns()
        risk_on, comment = _infer_risk_bias(perfs)

        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "created_at": time.time(),
            "risk_on": risk_on,
            "risk_comment": comment,
            "top_events": [],
            "top_moves": [],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/week/raw")
async def get_week_raw():
    """
    Données détaillées pour la grille et la table de la page macro :
    - asset_performances : [{symbol, name, return_pct}]
    - sentiment_grid     : [{date, bucket, sentiment, news_count}]
    """
    try:
        start, end = _current_week_range()
        perfs = _compute_weekly_returns()
        sentiment_grid = _build_dummy_sentiment_grid(start, end)

        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "created_at": time.time(),
            "asset_performances": perfs,
            "sentiment_grid": sentiment_grid,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bias")
async def get_bias():
    """
    Biais macro pour le dashboard principal :
    - résumé global (risk_on / label / commentaire)
    - perf hebdo par actif + biais simple par actif
    """
    try:
        start, end = _current_week_range()
        perfs = _compute_weekly_returns()
        risk_on, comment = _infer_risk_bias(perfs)

        def per_asset_bias(ret: float | None) -> str:
            if ret is None:
                return "neutral"
            if ret > 0.5:
                return "bullish"
            if ret < -0.5:
                return "bearish"
            return "neutral"

        assets_view = []
        for a in perfs:
            ret = a.get("return_pct")
            assets_view.append(
                {
                    "symbol": a["symbol"],
                    "name": a["name"],
                    "return_pct": ret,
                    "macro_bias": per_asset_bias(ret),
                }
            )

        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "created_at": time.time(),
            "risk_on": risk_on,                  # true / false / null
            "label": _risk_label_from_flag(risk_on),
            "comment": comment,
            "assets": assets_view,               # pour les petites lignes par actif si tu veux
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
