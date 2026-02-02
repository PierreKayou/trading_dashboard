# macro/schemas.py

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, HttpUrl


ImportanceLevel = Literal["low", "medium", "high"]
EventCategory = Literal[
    "inflation",
    "employment",
    "central_bank",
    "growth",
    "sentiment",
    "other",
]
NewsCategory = Literal[
    "macro",
    "company",
    "geopolitics",
    "tech",
    "other",
]
SentimentBucket = Literal[
    "macro_us",
    "macro_europe",
    "companies",
    "geopolitics",
    "tech",
]


class MacroEvent(BaseModel):
    id: str
    datetime: datetime
    country: str
    importance: ImportanceLevel
    category: EventCategory
    title: str

    actual: Optional[float] = None
    previous: Optional[float] = None
    consensus: Optional[float] = None
    unit: Optional[str] = None

    impact_asset: Optional[str] = None
    impact_move_pct: Optional[float] = None


class NewsItem(BaseModel):
    id: str
    datetime: datetime
    source: str
    headline: str
    url: HttpUrl

    tickers: List[str] = []
    sentiment: Optional[float] = None  # -1.0 .. 1.0
    category: NewsCategory = "other"


class AssetPerformance(BaseModel):
    symbol: str
    name: str
    period: Literal["day", "week", "month"]
    return_pct: float


class SentimentCell(BaseModel):
    date: date
    bucket: SentimentBucket
    sentiment: Optional[float] = None  # -1 .. 1
    news_count: int


class TopMove(BaseModel):
    description: str
    asset: str
    move_pct: float
    event_id: Optional[str] = None


class WeekMacroData(BaseModel):
    start: date
    end: date
    events: List[MacroEvent]
    news: List[NewsItem]
    asset_performances: List[AssetPerformance]
    sentiment_grid: List[SentimentCell]


class WeekMacroSummary(BaseModel):
    start: date
    end: date

    risk_on: Optional[bool]
    risk_comment: str

    top_events: List[MacroEvent]
    top_moves: List[TopMove]
    upcoming_focus: List[MacroEvent]


class MacroSeriesPoint(BaseModel):
    date: date
    value: float


class MacroSeries(BaseModel):
    name: str
    label: str
    points: List[MacroSeriesPoint]


class CountryMacroSnapshot(BaseModel):
    country: str
    inflation: Optional[float] = None
    policy_rate: Optional[float] = None
    unemployment: Optional[float] = None
    gdp_growth: Optional[float] = None


class MonthlyAssetPerformance(BaseModel):
    symbol: str
    name: str
    asset_class: str
    return_pct: float


class ThemeFrequency(BaseModel):
    theme: str
    count: int


class MonthlyMacroContext(BaseModel):
    month_start: date
    month_end: date

    cpi_vs_index: List[MacroSeries]
    policy_rate_vs_index: List[MacroSeries]

    country_snapshots: List[CountryMacroSnapshot]
    asset_performances: List[MonthlyAssetPerformance]
    themes: List[ThemeFrequency]
