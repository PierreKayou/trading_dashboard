# macro/router.py

from fastapi import APIRouter, HTTPException
import datetime as dt
import os
import time
import json

import yfinance as yf

router = APIRouter(
    prefix="/api/macro",
    tags=["macro"],
)

# Fichier partagé avec api.py (get_macro_state)
MACRO_STATE_FILE = os.path.join(os.getcwd(), "macro_state.json")

# Les mêmes actifs que sur le dashboard
SYMBOLS = {
    "ES": {"label": "S&P 500 Future", "yf": "ES=F"},
    "NQ": {"label": "Nasdaq 100 Future", "yf": "NQ=F"},
    "BTC": {"label": "Bitcoin", "yf": "BTC-USD"},
    "CL": {"label": "Crude Oil (WTI)", "yf": "CL=F"},
    "GC": {"label": "Gold", "yf": "GC=F"},
}


# ---------- Utilitaires ----------

def _week_range(today: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """Retourne (lundi, dimanche) pour la semaine courante."""
    if today is None:
        today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday())  # lundi
    end = start + dt.timedelta(days=6)                  # dimanche
    return start, end


def _load_state() -> dict | None:
    if not os.path.exists(MACRO_STATE_FILE):
        return None
    try:
        with open(MACRO_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_state(state: dict) -> None:
    try:
        with open(MACRO_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        # On ne crash pas pour un simple souci de fichier
        pass


def _is_same_week(state: dict, start: dt.date, end: dt.date) -> bool:
    try:
        return state.get("start") == start.isoformat() and state.get("end") == end.isoformat()
    except Exception:
        return False


def _compute_weekly_returns() -> list[dict]:
    """
    Calcule la performance hebdo approx pour chaque actif :
    dernier close vs close ~5 séances avant.
    Renvoie une liste :
    [
      {"symbol": "ES", "name": "S&P 500 Future", "return_pct": 1.23},
      ...
    ]
    """
    results: list[dict] = []

    for sym, cfg in SYMBOLS.items():
        yf_symbol = cfg["yf"]
        name = cfg["label"]

        try:
            ticker = yf.Ticker(yf_symbol)
            # 2 mois pour être large
            hist = ticker.history(period="2mo", interval="1d")
        except Exception:
            hist = None

        if hist is None or hist.empty or len(hist) < 6:
            results.append(
                {"symbol": sym, "name": name, "return_pct": None}
            )
            continue

        closes = hist["Close"].dropna()
        if len(closes) < 6:
            results.append(
                {"symbol": sym, "name": name, "return_pct": None}
            )
            continue

        last = float(closes.iloc[-1])
        last_week = float(closes.iloc[-6])

        if last_week == 0:
            ret = None
        else:
            ret = (last - last_week) / last_week * 100.0

        results.append(
            {
                "symbol": sym,
                "name": name,
                "return_pct": ret,
            }
        )

    return results


def _derive_risk_on(perfs: list[dict]) -> tuple[bool | None, str]:
    """
    Déduit un biais risk-on / risk-off très simple à partir d'ES, NQ et GC.
    """
    perf_map = {p["symbol"]: p["return_pct"] for p in perfs}

    es = perf_map.get("ES")
    nq = perf_map.get("NQ")
    gc = perf_map.get("GC")

    # Pas assez de données
    if es is None or nq is None or gc is None:
        return None, "Données partielles : impossible de déduire un biais macro hebdomadaire robuste."

    # règles simples
    if es > 0.5 and nq > 0.5 and gc <= 0.5:
        comment = (
            "Les indices actions US (S&P 500, Nasdaq) sont en hausse sur la semaine "
            "avec un or relativement stable ou en léger repli : environnement plutôt risk-on."
        )
        return True, comment

    if es < -0.5 and nq < -0.5 and gc > 0.5:
        comment = (
            "Les indices actions US reculent nettement tandis que l'or progresse : "
            "le marché adopte un biais défensif, plutôt risk-off."
        )
        return False, comment

    comment = (
        "Les performances hebdomadaires des indices et de l'or sont mitigées : "
        "le marché ne tranche pas clairement entre appétit pour le risque et mode défensif."
    )
    return None, comment


def _build_top_moves(perfs: list[dict]) -> list[dict]:
    """
    Sélectionne les mouvements les plus marquants (en valeur absolue) sur la semaine.
    """
    valid = [p for p in perfs if p["return_pct"] is not None]
    if not valid:
        return []

    # Tri par amplitude décroissante
    valid.sort(key=lambda x: abs(x["return_pct"]), reverse=True)
    top = valid[:4]

    moves: list[dict] = []
    for m in top:
        direction = "hausse" if m["return_pct"] > 0 else "baisse"
        moves.append(
            {
                "asset": m["symbol"],
                "description": f"{m['symbol']} ({m['name']}) en {direction} hebdomadaire marquée.",
                "move_pct": m["return_pct"],
            }
        )
    return moves


def _build_sentiment_grid(risk_on: bool | None, start: dt.date, end: dt.date) -> list[dict]:
    """
    Grille ultra simple pour la page macro :
    - dates de la semaine
    - buckets : macro_us, macro_europe, companies, geopolitics, tech
    On encode juste un sentiment global aligné sur risk_on.
    """
    buckets = ["macro_us", "macro_europe", "companies", "geopolitics", "tech"]
    days: list[dt.date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += dt.timedelta(days=1)

    # valeurs de base
    if risk_on is True:
        base = 0.3
    elif risk_on is False:
        base = -0.3
    else:
        base = 0.0

    grid: list[dict] = []
    for d in days:
        for b in buckets:
            # petit léger bruit pour ne pas être tout plat
            sent = base
            grid.append(
                {
                    "date": d.isoformat(),
                    "bucket": b,
                    "sentiment": sent,
                    "news_count": 3,  # valeur fictive mais > 0 pour l'affichage
                }
            )
    return grid


def _build_macro_state() -> dict:
    """
    Calcule / rafraîchit l'état macro hebdo complet :
    - perfs hebdo
    - biais risk-on / risk-off
    - top moves
    - grille de sentiment
    - métadonnées macro_regime, macro_factors, etc. (pour api.get_macro_state)
    """
    today = dt.date.today()
    start, end = _week_range(today)

    perfs = _compute_weekly_returns()
    risk_on, risk_comment = _derive_risk_on(perfs)
    top_moves = _build_top_moves(perfs)
    sentiment_grid = _build_sentiment_grid(risk_on, start, end)

    # Pour la section "top_events" de la page macro, on ne va pas
    # rebricoler tout le calendrier : on met quelques placeholders propres.
    top_events = [
        {
            "country": "US",
            "title": "Publications macro clés (emploi, activité, confiance)",
            "datetime": f"{start.isoformat()}T14:30:00Z",
            "importance": "high",
            "actual": None,
            "previous": None,
            "consensus": None,
            "unit": None,
        },
        {
            "country": "EU",
            "title": "Données d'inflation / croissance en Zone Euro",
            "datetime": f"{(start + dt.timedelta(days=2)).isoformat()}T10:00:00Z",
            "importance": "medium",
            "actual": None,
            "previous": None,
            "consensus": None,
            "unit": None,
        },
    ]

    # Construction d'un "macro_regime" exploitable par api.get_macro_state()
    if risk_on is True:
        regime_label = "Régime plutôt risk-on (actions soutenues)"
        rates_pressure = "neutre"
        equities_bias = "biais haussier modéré sur les indices actions"
    elif risk_on is False:
        regime_label = "Régime plutôt risk-off (flux défensifs)"
        rates_pressure = "restrictive"
        equities_bias = "biais prudent / baissier sur les indices actions"
    else:
        regime_label = "Régime macro neutre / indéterminé"
        rates_pressure = "neutre"
        equities_bias = "contexte neutre, pas de biais directionnel tranché"

    macro_state = {
        # métadonnées globales
        "timestamp": time.time(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "risk_on": risk_on,
        "risk_comment": risk_comment,
        "top_events": top_events,
        "top_moves": top_moves,
        "asset_performances": perfs,
        "sentiment_grid": sentiment_grid,

        # structure plus macro pour api.get_macro_state()
        "macro_regime": {
            "label": regime_label,
            "confidence": 0.6,
            "stability": "stable" if risk_on is not None else "incertain",
        },
        "macro_factors": {
            "monetary_policy": "neutre",
            "inflation_trend": "stable",
            "growth_trend": "stable",
            "risk_sentiment": "risk-on" if risk_on is True else ("risk-off" if risk_on is False else "neutre"),
            "rates_pressure": rates_pressure,
            "usd_bias": "neutre",
        },
        "market_bias": {
            "equities": equities_bias,
            "indices_us": equities_bias,
            "commodities": "contexte mixte selon les sous-classes",
            "crypto": "sensibilité forte au sentiment risk-on / risk-off hebdo",
        },
        "invalidations": [],
        "commentary": risk_comment,
    }

    return macro_state


def _get_or_refresh_state() -> dict:
    """
    Récupère l'état macro hebdo depuis le fichier,
    ou le recalcule si la semaine a changé ou si le fichier n'existe pas.
    """
    today = dt.date.today()
    start, end = _week_range(today)

    state = _load_state()
    if state is not None and _is_same_week(state, start, end):
        return state

    # recalcul
    state = _build_macro_state()
    _save_state(state)
    return state


# ---------- Endpoints publics ----------

@router.get("/week/summary")
async def get_week_summary():
    """
    Vue synthétique pour la page macro :
    - start / end
    - risk_on / risk_comment
    - top_events / top_moves
    """
    try:
        state = _get_or_refresh_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur macro: {e}")

    return {
        "start": state.get("start"),
        "end": state.get("end"),
        "risk_on": state.get("risk_on"),
        "risk_comment": state.get("risk_comment"),
        "top_events": state.get("top_events", []),
        "top_moves": state.get("top_moves", []),
    }


@router.get("/week/raw")
async def get_week_raw():
    """
    Données détaillées pour la grille et la table de la page macro :
    - asset_performances : [{symbol, name, return_pct}]
    - sentiment_grid : [{date, bucket, sentiment, news_count}]
    """
    try:
        state = _get_or_refresh_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur macro: {e}")

    return {
        "asset_performances": state.get("asset_performances", []),
        "sentiment_grid": state.get("sentiment_grid", []),
    }


@router.get("/bias")
async def get_bias():
    """
    Biais macro par actif (utilisé par l'index pour les petites lignes 'Biais macro haussier / baissier / neutre').
    """
    try:
        state = _get_or_refresh_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur macro: {e}")

    assets_bias: dict[str, dict] = {}

    for perf in state.get("asset_performances", []):
        sym = perf.get("symbol")
        if not sym:
            continue

        ret = perf.get("return_pct")
        if ret is None:
            bias = "neutral"
            reason = "Pas de donnée hebdomadaire exploitable pour cet actif."
        elif ret > 0.5:
            bias = "bullish"
            reason = f"Performance hebdo positive (~{ret:.1f} %)."
        elif ret < -0.5:
            bias = "bearish"
            reason = f"Performance hebdo négative (~{ret:.1f} %)."
        else:
            bias = "neutral"
            reason = f"Mouvement hebdomadaire limité (~{ret:.1f} %)."

        assets_bias[sym] = {
            "bias": bias,
            "reason": reason,
        }

    return {"assets": assets_bias}
