###############################
# macro/router.py
###############################
from fastapi import APIRouter
from typing import Dict, Any, List
import datetime as dt
import time

from .service import build_week_raw, ASSETS

router = APIRouter(
    prefix="/api/macro",
    tags=["macro"],
)


# --------------------------------------------------
# Helpers communs
# --------------------------------------------------
def _get_week_range(base: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """
    Retourne (start, end) de la semaine courante :
    - start = lundi
    - end   = dimanche
    """
    if base is None:
        base = dt.date.today()
    start = base - dt.timedelta(days=base.weekday())  # lundi
    end = start + dt.timedelta(days=6)                # dimanche
    return start, end


def _compute_risk_profile(asset_perfs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Déduit un biais risk-on / risk-off global à partir
    des performances hebdo des actifs suivis.
    """
    if not asset_perfs:
        return {
            "risk_on": None,
            "label": "Lecture macro mitigée",
            "comment": (
                "Impossible de déterminer un biais clair : pas assez de données "
                "ou performances trop neutres."
            ),
        }

    rets = [a.get("return_pct") or 0.0 for a in asset_perfs]
    positives = sum(1 for r in rets if r > 0)
    negatives = sum(1 for r in rets if r < 0)
    avg = sum(rets) / len(rets)

    # Logique simple & lisible : on regarde la répartition + l'amplitude moyenne.
    if avg > 0.5 or positives - negatives >= 2:
        risk_on = True
        label = "Biais macro global : risk-on"
        comment = (
            "Biais plutôt risk-on : les actifs risqués s'inscrivent globalement en hausse "
            "cette semaine, dans un contexte plus favorable au risque."
        )
    elif avg < -0.5 or negatives - positives >= 2:
        risk_on = False
        label = "Biais macro global : risk-off"
        comment = (
            "Biais plutôt risk-off : la majorité des actifs sont sous pression cette semaine, "
            "avec un contexte plus défensif sur les marchés."
        )
    else:
        risk_on = None
        label = "Lecture macro mitigée"
        comment = (
            "Lecture macro mitigée : les performances hebdomadaires des actifs sont "
            "mélangées, sans biais clair en faveur du risk-on ou du risk-off."
        )

    return {"risk_on": risk_on, "label": label, "comment": comment}


def _build_top_moves(asset_perfs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sélectionne quelques mouvements marquants sur la semaine, en absolu.
    Renvoie une liste de dicts :
      { asset, move_pct, description }
    """
    if not asset_perfs:
        return []

    # On trie par mouvement absolu décroissant
    sorted_assets = sorted(
        asset_perfs,
        key=lambda a: abs(a.get("return_pct") or 0.0),
        reverse=True,
    )

    moves: List[Dict[str, Any]] = []
    for a in sorted_assets:
        pct = a.get("return_pct") or 0.0
        # On ignore les moves insignifiants (< 1 % en absolu)
        if abs(pct) < 1.0:
            continue

        sym = a.get("symbol") or "?"
        name = a.get("name") or ""
        sign = "+" if pct > 0 else ""
        desc = f"{sym} ({name}) en {'hausse' if pct > 0 else 'baisse'} de {sign}{pct:.2f} % sur la semaine."

        moves.append(
            {
                "asset": sym,
                "move_pct": pct,
                "description": desc,
            }
        )

    # On se limite à 3 mouvements marquants max pour garder la carte lisible
    return moves[:3]


def _macro_bias_for_return(pct: float) -> str:
    """
    Traduit une perf hebdo en biais macro simple pour l'actif :
    - pct >= +0.5 %  -> 'bullish'
    - pct <= -0.5 %  -> 'bearish'
    - sinon          -> 'neutral'
    """
    if pct >= 0.5:
        return "bullish"
    if pct <= -0.5:
        return "bearish"
    return "neutral"


# --------------------------------------------------
# Endpoints
# --------------------------------------------------

@router.get("/week/raw")
def get_week_raw() -> Dict[str, Any]:
    """
    Données détaillées pour la grille et la table de la page macro :

    - asset_performances : [{symbol, name, return_pct}]
    - sentiment_grid     : [{date, bucket, sentiment, news_count}]
    """
    start, end = _get_week_range()
    data = build_week_raw(start, end)
    return data


@router.get("/week/summary")
def get_week_summary() -> Dict[str, Any]:
    """
    Vue synthétique pour la page macro :

    - start / end
    - risk_on / risk_comment
    - top_events
    - top_moves
    """
    start, end = _get_week_range()
    raw = build_week_raw(start, end)

    asset_perfs = raw.get("asset_performances", []) or []

    risk_profile = _compute_risk_profile(asset_perfs)
    top_moves = _build_top_moves(asset_perfs)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "created_at": time.time(),
        "risk_on": risk_profile["risk_on"],
        "risk_comment": risk_profile["comment"],
        "top_events": [],  # pourra être rempli plus tard avec un vrai calendrier/news
        "top_moves": top_moves,
    }


@router.get("/bias")
def get_bias() -> Dict[str, Any]:
    """
    Biais macro par actif (utilisé par l'index pour les petites lignes
    'Biais macro haussier / baissier / neutre').
    """
    start, end = _get_week_range()
    raw = build_week_raw(start, end)
    asset_perfs = raw.get("asset_performances", []) or []

    risk_profile = _compute_risk_profile(asset_perfs)

    assets_out: List[Dict[str, Any]] = []
    for a in asset_perfs:
        sym = a.get("symbol") or "?"
        name = a.get("name") or ASSETS.get(sym, {}).get("name", sym)
        pct = a.get("return_pct") or 0.0
        macro_bias = _macro_bias_for_return(pct)

        assets_out.append(
            {
                "symbol": sym,
                "name": name,
                "return_pct": pct,
                "macro_bias": macro_bias,
            }
        )

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "created_at": time.time(),
        "risk_on": risk_profile["risk_on"],
        "label": risk_profile["label"],
        "comment": risk_profile["comment"],
        "assets": assets_out,
    }
