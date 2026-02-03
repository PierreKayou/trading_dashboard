# macro/router.py

from fastapi import APIRouter, HTTPException
import yfinance as yf
from datetime import date, timedelta
import time
from typing import List, Dict, Any, Optional

router = APIRouter(
    prefix="/api/macro",
    tags=["macro"],
)

# Même univers d’actifs que sur le dashboard principal
SYMBOLS = {
    "ES": {"name": "S&P 500 Future", "yf": "ES=F"},
    "NQ": {"name": "Nasdaq 100 Future", "yf": "NQ=F"},
    "BTC": {"name": "Bitcoin", "yf": "BTC-USD"},
    "CL": {"name": "Crude Oil (WTI)", "yf": "CL=F"},
    "GC": {"name": "Gold", "yf": "GC=F"},
}


# ------------------------------------------------------------
# Helpers : semaine courante & calcul de perf hebdo
# ------------------------------------------------------------
def get_week_bounds(today: Optional[date] = None) -> tuple[date, date]:
    """
    Retourne (lundi, dimanche) de la semaine du jour.
    """
    if today is None:
        today = date.today()
    monday = today - timedelta(days=today.weekday())  # 0 = lundi
    sunday = monday + timedelta(days=6)
    return monday, sunday


def weekly_return_pct(yf_symbol: str, start: date, end: date) -> Optional[float]:
    """
    Perf % entre le premier close de la semaine et le dernier close de la semaine.
    Si on n'a pas assez de données, renvoie None.
    """
    try:
        ticker = yf.Ticker(yf_symbol)
        # end + 1 jour pour être sûr de capter le dernier close
        hist = ticker.history(
            start=start,
            end=end + timedelta(days=1),
            interval="1d",
        )
    except Exception:
        return None

    if hist.empty or len(hist["Close"].dropna()) < 2:
        return None

    closes = hist["Close"].dropna()
    first = float(closes.iloc[0])
    last = float(closes.iloc[-1])
    if first == 0:
        return None

    return (last - first) / first * 100.0


def build_asset_performances(week_start: date, week_end: date) -> List[Dict[str, Any]]:
    assets: List[Dict[str, Any]] = []

    for sym, cfg in SYMBOLS.items():
        ret = weekly_return_pct(cfg["yf"], week_start, week_end)
        assets.append(
            {
                "symbol": sym,
                "name": cfg["name"],
                "return_pct": ret,
            }
        )

    return assets


def compute_risk_on_comment(assets: List[Dict[str, Any]]) -> tuple[Optional[bool], str]:
    """
    Déduit un biais risk-on / risk-off simple à partir des perfs hebdo.
    """
    rets = [a["return_pct"] for a in assets if a["return_pct"] is not None]
    if not rets:
        return None, "Impossible d'évaluer le biais macro : données hebdos insuffisantes."

    positives = sum(1 for r in rets if r > 0.2)
    negatives = sum(1 for r in rets if r < -0.2)

    if positives >= 3 and positives > negatives:
        # Risk-on
        return (
            True,
            "Biais plutôt risk-on : la majorité des actifs progresse cette semaine, "
            "avec un contexte global plus constructif sur les marchés.",
        )
    elif negatives >= 3 and negatives > positives:
        # Risk-off
        return (
            False,
            "Biais plutôt risk-off : la majorité des actifs sont sous pression cette semaine, "
            "avec un contexte plus défensif sur les marchés.",
        )
    else:
        # Neutre / mixte
        return (
            None,
            "Lecture macro mitigée : les performances hebdomadaires des actifs sont "
            "mélangées, sans biais clair en faveur du risk-on ou du risk-off.",
        )


def build_top_moves(assets: List[Dict[str, Any]], max_items: int = 3) -> List[Dict[str, Any]]:
    """
    Sélectionne les mouvements les plus marquants de la semaine.
    - Triés par |perf| décroissante
    - Filtre sur un seuil minimal (1 % en absolu)
    """
    # On ne garde que ceux qui ont une perf
    valid = [a for a in assets if a["return_pct"] is not None]

    # Tri par amplitude décroissante
    valid.sort(key=lambda x: abs(x["return_pct"]), reverse=True)

    top: List[Dict[str, Any]] = []
    for a in valid:
        if len(top) >= max_items:
            break
        move = a["return_pct"]
        if abs(move) < 1.0:
            # on ignore les micro-mouvements
            continue

        direction = "hausse" if move > 0 else "baisse"
        sign = "+" if move > 0 else ""
        desc = (
            f"{a['symbol']} ({a['name']}) en {direction} de "
            f"{sign}{move:.2f} % sur la semaine."
        )

        top.append(
            {
                "asset": a["symbol"],
                "move_pct": move,
                "description": desc,
            }
        )

    return top


def build_sentiment_grid(week_start: date, week_end: date) -> List[Dict[str, Any]]:
    """
    Pour l'instant : grille neutre (0, 0 news).
    Structure prête pour version B (news & IA).
    """
    buckets = ["macro_us", "macro_europe", "companies", "geopolitics", "tech"]
    grid: List[Dict[str, Any]] = []

    d = week_start
    while d <= week_end:
        for b in buckets:
            grid.append(
                {
                    "date": d.isoformat(),
                    "bucket": b,
                    "sentiment": 0,   # neutre
                    "news_count": 0,  # aucune news encore
                }
            )
        d += timedelta(days=1)

    return grid


# ------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------

@router.get("/week/summary")
async def get_week_summary():
    """
    Vue synthétique pour la page macro :

    - start / end
    - risk_on / risk_comment
    - top_events / top_moves
    """
    week_start, week_end = get_week_bounds()
    assets = build_asset_performances(week_start, week_end)
    risk_on, comment = compute_risk_on_comment(assets)
    top_moves = build_top_moves(assets, max_items=3)

    return {
        "start": week_start.isoformat(),
        "end": week_end.isoformat(),
        "created_at": time.time(),
        "risk_on": risk_on,
        "risk_comment": comment,
        "top_events": [],       # on les remplira plus tard (version C avec IA macro)
        "top_moves": top_moves,
    }


@router.get("/week/raw")
async def get_week_raw():
    """
    Données détaillées pour la grille et la table de la page macro :

    - asset_performances : [{symbol, name, return_pct}]
    - sentiment_grid : [{date, bucket, sentiment, news_count}]
    """
    week_start, week_end = get_week_bounds()
    assets = build_asset_performances(week_start, week_end)
    sentiment_grid = build_sentiment_grid(week_start, week_end)

    return {
        "start": week_start.isoformat(),
        "end": week_end.isoformat(),
        "created_at": time.time(),
        "asset_performances": assets,
        "sentiment_grid": sentiment_grid,
    }


@router.get("/bias")
async def get_bias():
    """
    Biais macro par actif (utilisé par l'index pour les petites lignes
    'Biais macro haussier / baissier / neutre').
    """
    week_start, week_end = get_week_bounds()
    assets = build_asset_performances(week_start, week_end)
    risk_on, comment = compute_risk_on_comment(assets)

    # Label global
    if risk_on is True:
        label = "Biais macro global : risk-on"
    elif risk_on is False:
        label = "Biais macro global : risk-off"
    else:
        label = "Biais macro global : neutre / mitigé"

    # Biais par actif, basé sur le retour hebdo
    classified_assets: List[Dict[str, Any]] = []
    for a in assets:
        ret = a["return_pct"]
        if ret is None:
            bias = "neutral"
        elif ret > 1.0:
            bias = "bullish"
        elif ret < -1.0:
            bias = "bearish"
        else:
            bias = "neutral"

        classified_assets.append(
            {
                "symbol": a["symbol"],
                "name": a["name"],
                "return_pct": ret,
                "macro_bias": bias,
            }
        )

    return {
        "start": week_start.isoformat(),
        "end": week_end.isoformat(),
        "created_at": time.time(),
        "risk_on": risk_on,
        "label": label,
        "comment": comment,
        "assets": classified_assets,
    }
