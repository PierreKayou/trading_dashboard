# macro/service.py

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import List, Tuple

from .schemas import (
    WeekMacroData,
    WeekMacroSummary,
    MonthlyMacroContext,
    MacroSeries,
    AssetPerformance,
    SentimentCell,
    TopMove,
)
from .providers import (
    fetch_economic_calendar_week,
    fetch_news_for_period,
    _bucket_from_news,
    _demo_asset_performances,
    fetch_fred_series,
    fetch_country_snapshots_demo,
    _demo_asset_performances as _demo_month_assets,
    build_theme_frequencies_demo,
)


# ---------------------------------------------------------------------------
# Week view
# ---------------------------------------------------------------------------

async def get_week_macro_data(start: date, end: date) -> WeekMacroData:
    # 1. Événements macro
    events = await fetch_economic_calendar_week(start, end)

    # 2. News
    news = await fetch_news_for_period(start, end)

    # 3. Performances hebdo (MVP : démo ou plus tard vrai provider marché)
    asset_performances: List[AssetPerformance] = _demo_asset_performances("week")

    # 4. Heatmap sentiment
    sentiment_cells: List[SentimentCell] = []
    grouped: dict[Tuple[date, str], List[float]] = defaultdict(list)
    counts: dict[Tuple[date, str], int] = defaultdict(int)

    for n in news:
        b = _bucket_from_news(n)
        key = (n.datetime.date(), b)
        if n.sentiment is not None:
            grouped[key].append(n.sentiment)
        counts[key] += 1

    # Construire une grille complète sur la semaine
    buckets = ["macro_us", "macro_europe", "companies", "geopolitics", "tech"]
    current = start
    while current <= end:
        for b in buckets:
            key = (current, b)
            values = grouped.get(key, [])
            avg = sum(values) / len(values) if values else None
            cnt = counts.get(key, 0)
            sentiment_cells.append(
                SentimentCell(date=current, bucket=b, sentiment=avg, news_count=cnt)
            )
        current += timedelta(days=1)

    return WeekMacroData(
        start=start,
        end=end,
        events=events,
        news=news,
        asset_performances=asset_performances,
        sentiment_grid=sentiment_cells,
    )


async def summarize_week(data: WeekMacroData) -> WeekMacroSummary:
    # Risk-on/off simple : moyenne des retours hebdo (hors VIX).
    rets = [
        a.return_pct
        for a in data.asset_performances
        if a.symbol.upper() not in {"VIX"}
    ]
    avg_ret = sum(rets) / len(rets) if rets else 0.0
    risk_on = avg_ret > 0

    if avg_ret > 1.0:
        risk_comment = "Semaine globalement risk-on, les indices actions ont bien progressé."
    elif avg_ret > 0.0:
        risk_comment = "Semaine légèrement positive sur les actions, ton marché reste plutôt constructif."
    elif avg_ret < -1.0:
        risk_comment = "Semaine franchement risk-off, les indices actions ont reculé."
    elif avg_ret < 0.0:
        risk_comment = "Semaine légèrement négative sur les actions, prudence mais sans panique."
    else:
        risk_comment = "Semaine neutre, pas de prise de direction très marquée sur les indices."

    # Top events : on prend les plus importants + tri par importance / pays
    sorted_events = sorted(
        data.events,
        key=lambda e: (
            {"high": 2, "medium": 1, "low": 0}.get(e.importance, 0),
            e.datetime,
        ),
        reverse=True,
    )
    top_events = sorted_events[:5]

    # Top moves : on exploite impact_move_pct si renseigné (démo ou plus tard calcul réel)
    events_with_move = [e for e in data.events if e.impact_move_pct is not None]
    sorted_moves = sorted(
        events_with_move,
        key=lambda e: abs(e.impact_move_pct or 0),
        reverse=True,
    )
    top_moves: List[TopMove] = []
    for e in sorted_moves[:5]:
        desc = f"{e.title} ({e.country})"
        top_moves.append(
            TopMove(
                description=desc,
                asset=e.impact_asset or "ES",
                move_pct=e.impact_move_pct or 0.0,
                event_id=e.id,
            )
        )

    # Upcoming : on prend les events à partir de demain (dans la même semaine)
    today = date.today()
    upcoming = [
        e
        for e in data.events
        if e.datetime.date() >= today and e.datetime.date() <= data.end
    ]
    upcoming_sorted = sorted(upcoming, key=lambda e: e.datetime)[:5]

    return WeekMacroSummary(
        start=data.start,
        end=data.end,
        risk_on=risk_on,
        risk_comment=risk_comment,
        top_events=top_events,
        top_moves=top_moves,
        upcoming_focus=upcoming_sorted,
    )


# ---------------------------------------------------------------------------
# Monthly context view
# ---------------------------------------------------------------------------

async def get_monthly_macro_context(month_start: date, month_end: date) -> MonthlyMacroContext:
    # CPI US vs S&P (proxy SP500 sur FRED : SP500 ; inflation CPIAUCSL)
    cpi_series = await fetch_fred_series("CPIAUCSL")
    spx_series = await fetch_fred_series("SP500")

    # Taux directeurs vs index (proxy : FEDFUNDS vs SP500)
    fed_funds = await fetch_fred_series("FEDFUNDS")

    # Snapshots pays (démo pour l'instant)
    snapshots = await fetch_country_snapshots_demo()

    # Performances mensuelles par classe d’actifs (démo)
    month_assets: List[MonthlyAssetPerformance] = _demo_month_assets("month")

    # Thèmes dominants (démo)
    themes = await build_theme_frequencies_demo()

    # On pourrait filtrer les séries sur le mois ici si tu veux plus court,
    # mais garder toute la série est souvent utile pour du graphique de contexte.
    cpi_vs_index = [cpi_series, spx_series]
    policy_rate_vs_index = [fed_funds, spx_series]

    return MonthlyMacroContext(
        month_start=month_start,
        month_end=month_end,
        cpi_vs_index=cpi_vs_index,
        policy_rate_vs_index=policy_rate_vs_index,
        country_snapshots=snapshots,
        asset_performances=month_assets,
        themes=themes,
    )
