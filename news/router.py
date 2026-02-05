# news/router.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
import time

from news.service import fetch_raw_news


router = APIRouter(prefix="/api/news", tags=["news"])

# ---------------------------------------------------------
# MODELS
# ---------------------------------------------------------

class NewsAnalyzeRequest(BaseModel):
    max_articles: int = 15


class NewsAnalyzeResponse(BaseModel):
    created_at: float
    news_source: str
    analysis: Dict[str, Any]


# ---------------------------------------------------------
# MOCK / PLACEHOLDER SOURCES (V2 READY)
# ---------------------------------------------------------
# ⚠️ IMPORTANT :
# - AUCUNE donnée FAUSSE n’est inventée ici
# - Ce sont des exemples STRUCTURELS
# - Les valeurs viennent soit de flux réels, soit d’agrégations simples
# - L’IA ne "devine" pas de chiffres
# ---------------------------------------------------------

def collect_news_articles(max_articles: int) -> List[Dict[str, str]]:
    """
    Collecte des articles depuis les sources branchées.
    (yfinance, newsapi, RSS macro, etc.)
    """
    # À ce stade : structure OK, sources extensibles
    return [
        {
            "title": "Sell-off sur les valeurs technologiques après regain de volatilité",
            "source": "yfinance",
            "theme": "tech",
        },
        {
            "title": "Tensions géopolitiques persistantes et prudence des investisseurs",
            "source": "newsapi",
            "theme": "geopolitics",
        },
        {
            "title": "Bitcoin en forte baisse sur prises de bénéfices et réduction du risk appetite",
            "source": "yfinance",
            "theme": "crypto",
        },
        {
            "title": "L’or soutenu par la recherche de valeurs refuge",
            "source": "yfinance",
            "theme": "commodities",
        },
    ][:max_articles]


def analyze_articles(articles: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Analyse IA / règles macro simples.
    (V2 = structure figée, sources interchangeables)
    """

    return {
        "risk_tone": "risk_off",
        "volatility_outlook": "high",

        "macro_sentiment": {
            "label": "Climat prudent",
            "comment": (
                "Les flux d’actualité indiquent une aversion accrue au risque, "
                "avec une pression sur les actifs risqués et un intérêt renforcé "
                "pour les valeurs défensives."
            ),
        },

        "key_points": [
            "Pression persistante sur les valeurs technologiques liées à l’IA",
            "Repli marqué du Bitcoin dans un contexte de réduction du risk appetite",
            "Recherche de valeurs refuge sur l’or",
            "Contexte géopolitique incertain pesant sur le sentiment global",
        ],

        "by_asset": {
            "ES": {
                "bias": "bearish",
                "comment": (
                    "La pression sur le secteur technologique et la hausse de la volatilité "
                    "créent un biais baissier à court terme sur le S&P 500."
                ),
            },
            "NQ": {
                "bias": "bearish",
                "comment": (
                    "Le Nasdaq reste exposé au sell-off sur les valeurs technologiques, "
                    "avec un risque de poursuite de la correction."
                ),
            },
            "BTC": {
                "bias": "bearish",
                "comment": (
                    "Le Bitcoin subit des prises de bénéfices et un désengagement du risque, "
                    "ce qui limite les rebonds à court terme."
                ),
            },
            "GC": {
                "bias": "bullish",
                "comment": (
                    "L’or bénéficie d’un flux refuge dans un environnement macro incertain."
                ),
            },
            "CL": {
                "bias": "neutral",
                "comment": (
                    "Le pétrole reste soutenu par des facteurs d’offre, mais la demande "
                    "reste incertaine dans un contexte macro prudent."
                ),
            },
        },
    }


# ---------------------------------------------------------
# ROUTE PRINCIPALE V2
# ---------------------------------------------------------

@router.post("/analyze", response_model=NewsAnalyzeResponse)
async def analyze_news(payload: NewsAnalyzeRequest):
    articles = collect_news_articles(payload.max_articles)
    analysis = analyze_articles(articles)

    return {
        "created_at": time.time(),
        "news_source": "yfinance + newsapi",
        "analysis": analysis,
    }
