# macro/router.py

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from .schemas import WeekMacroData, WeekMacroSummary, MonthlyMacroContext
from .service import (
    get_week_macro_data,
    summarize_week,
    get_monthly_macro_context,
)

router = APIRouter(prefix="/macro", tags=["macro"])


def _default_week_range() -> tuple[date, date]:
    today = date.today()
    # On prend la semaine "courante" : lundi → dimanche
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


@router.get("/week/raw", response_model=WeekMacroData)
async def get_week_raw(
    start: Optional[date] = Query(None, description="Début de semaine (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="Fin de semaine (YYYY-MM-DD)"),
):
    """
    Donne toutes les données brutes nécessaires à la vue “Semaine” :
    - événements macro
    - news
    - performances hebdo
    - grille de sentiment (heatmap)
    """
    if not start or not end:
        start, end = _default_week_range()
    return await get_week_macro_data(start, end)


@router.get("/week/summary", response_model=WeekMacroSummary)
async def get_week_summary(
    start: Optional[date] = Query(None, description="Début de semaine (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="Fin de semaine (YYYY-MM-DD)"),
):
    """
    Résumé structuré de la semaine :
    - risk-on / risk-off
    - top events
    - top moves
    - événements à surveiller pour le reste de la semaine
    """
    if not start or not end:
        start, end = _default_week_range()

    data = await get_week_macro_data(start, end)
    return await summarize_week(data)


@router.get("/month/context", response_model=MonthlyMacroContext)
async def get_month_context(
    month_start: Optional[date] = Query(
        None, description="Début du mois (YYYY-MM-DD, par défaut : 1er du mois courant)"
    ),
    month_end: Optional[date] = Query(
        None, description="Fin du mois (YYYY-MM-DD, par défaut : dernier jour du mois courant)"
    ),
):
    """
    Vue “contexte macro mensuel” :
    - séries CPI vs indice
    - séries taux directeurs vs indice
    - tableau comparatif macro par pays
    - performances mensuelles par classes d’actifs
    - thèmes dominants des news
    """
    today = date.today()

    if month_start is None:
        month_start = today.replace(day=1)

    if month_end is None:
        # calcul fin de mois
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1, day=1)
        month_end = next_month - timedelta(days=1)

    return await get_monthly_macro_context(month_start, month_end)
