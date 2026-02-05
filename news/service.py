# news/service.py

from __future__ import annotations

from typing import List, Dict, Any, Optional
import time
import datetime as dt

import yfinance as yf


# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

# Symboles utilisés pour récupérer des news via yfinance
NEWS_SYMBOLS = [
    "^GSPC",    # S&P 500
    "^NDX",     # Nasdaq 100
    "CL=F",     # Crude Oil Future
    "GC=F",     # Gold Future
    "BTC-USD",  # Bitcoin
]


# ------------------------------------------------------------------
# HELPERS : YFINANCE NEWS
# ------------------------------------------------------------------

def _fetch_yfinance_news(max_articles: int = 50) -> List[Dict[str, Any]]:
    """
    Récupère les news via yfinance (Ticker.news) sur quelques symboles clés.
    Retourne une LISTE d'articles, chaque article étant un dict simple.

    Format d'un article :
    {
        "symbol": "ES" / "^GSPC" / "BTC-USD" / ...,
        "title": "Titre de la news",
        "publisher": "Nom de la source",
        "link": "https://…",
        "providerPublishTime": 1700000000,  # timestamp
    }
    """
    articles: List[Dict[str, Any]] = []
    seen_titles = set()

    for sym in NEWS_SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            items = ticker.news or []
        except Exception:
            continue

        for item in items:
            title = item.get("title")
            if not title or title in seen_titles:
                continue

            seen_titles.add(title)
            articles.append(
                {
                    "symbol": sym,
                    "title": title,
                    "publisher": item.get("publisher"),
                    "link": item.get("link"),
                    "providerPublishTime": item.get("providerPublishTime"),
                }
            )

    # On tronque au max demandé
    return articles[:max_articles]


# ------------------------------------------------------------------
# API PUBLIQUE 1 : fetch_raw_news (pour macro.service)
# ------------------------------------------------------------------

def fetch_raw_news(
    max_articles: int = 50,
    days_back: int = 7,
    symbols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Fonction de compatibilité utilisée par macro/service.py.

    Elle doit renvoyer un DICT avec au moins les clés :
    - "source": str
    - "fetched_at": timestamp
    - "articles": List[Dict[str, Any]]

    macro/service._build_sentiment_grid() fait ensuite :
        raw = fetch_raw_news(max_articles=400)
        articles = raw.get("articles", [])
    """

    # Pour l'instant, on utilise uniquement yfinance comme source gratuite.
    # On pourrait ajouter d'autres sources plus tard (NewsAPI, etc.).
    arts = _fetch_yfinance_news(max_articles=max_articles)

    # Filtrage par "days_back" si on veut être propre
    if days_back is not None and days_back > 0:
        cutoff = dt.datetime.utcnow() - dt.timedelta(days=days_back)
        filtered: List[Dict[str, Any]] = []

        for a in arts:
            ts = a.get("providerPublishTime")
            if not ts:
                continue

            # Correction ms -> s éventuelle
            if ts > 10_000_000_000:
                ts = ts / 1000

            try:
                d = dt.datetime.utcfromtimestamp(ts)
            except Exception:
                continue

            if d >= cutoff:
                filtered.append(a)

        arts = filtered

    return {
        "source": "yfinance",
        "fetched_at": time.time(),
        "articles": arts,
    }


# ------------------------------------------------------------------
# API PUBLIQUE 2 : build_stress_report (pour news.router V2)
# ------------------------------------------------------------------

def build_stress_report(
    symbols: Optional[List[str]] = None,
    max_articles: int = 50,
    days_back: int = 3,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Fonction appelée par le nouveau router V2 (/api/news/stress).

    On renvoie pour l'instant un STUB “neutre” suffisamment structuré
    pour que le backend démarre et que le frontend puisse afficher
    quelque chose de cohérent si jamais on consomme cette route.

    TODO (plus tard) :
    - réutiliser fetch_raw_news(...) pour récupérer les news brutes
    - scorer le flux (risk-on / risk-off, volatilité, par actif, etc.)
    - calculer un true "stress report" macro/market.
    """

    universe = symbols or ["ES", "NQ", "BTC", "CL", "GC"]

    # Pour l'instant on ne recalcule pas les news ici → stub
    return {
        "source": "stub",
        "generated_at": time.time(),
        "params": {
            "symbols": universe,
            "max_articles": max_articles,
            "days_back": days_back,
        },
        "global_stress": {
            "score": 0.0,
            "label": "Neutre",
            "comment": (
                "Analyse de stress V2 non encore implémentée côté service. "
                "Stub neutre renvoyé par défaut."
            ),
        },
        "by_asset": {
            sym: {
                "stress_score": 0.0,
                "bias": "neutral",
                "comment": "Pas d'analyse spécifique pour cet actif (stub).",
            }
            for sym in universe
        },
        "raw_articles_used": [],
    }
