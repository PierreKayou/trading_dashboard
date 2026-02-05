# news/service.py

from typing import List, Dict, Any
import os
import time

import yfinance as yf
import httpx

# ------------------------------------------------------------------
# CONFIG : NewsAPI (https://newsapi.org) pour compléter yfinance
# ------------------------------------------------------------------
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"

# Symbols utilisés pour les news yfinance
NEWS_SYMBOLS = [
    "^GSPC",    # S&P 500
    "^NDX",     # Nasdaq 100
    "CL=F",     # Crude Oil Future
    "GC=F",     # Gold Future
    "BTC-USD",  # Bitcoin
]


def fetch_yfinance_news(max_articles: int = 30) -> List[Dict[str, Any]]:
    """
    Récupère les news via yfinance (Ticker.news) sur quelques symboles clés.
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

    return articles


def fetch_newsapi_news(max_articles: int = 30) -> List[Dict[str, Any]]:
    """
    Récupère des news business / macro via NewsAPI.
    Si NEWS_API_KEY n'est pas définie, on renvoie une liste vide.
    """
    if not NEWS_API_KEY:
        return []

    params = {
        "category": "business",
        "language": "en",
        "pageSize": max_articles,
    }

    try:
        with httpx.Client(timeout=8.0) as http_client:
            resp = http_client.get(
                NEWS_API_URL,
                params=params,
                headers={"X-Api-Key": NEWS_API_KEY},
            )
    except Exception:
        return []

    if resp.status_code != 200:
        return []

    data = resp.json()
    raw_articles = data.get("articles", []) or []

    articles: List[Dict[str, Any]] = []
    for art in raw_articles:
        title = art.get("title")
        if not title:
            continue

        src = art.get("source") or {}
        publisher = src.get("name") or "?"

        articles.append(
            {
                "symbol": "global",   # NewsAPI ne donne pas de symbole, on marque 'global'
                "title": title,
                "publisher": publisher,
                "link": art.get("url"),
                "providerPublishTime": None,
            }
        )

    return articles


def fetch_raw_news(max_articles: int = 30) -> Dict[str, Any]:
    """
    Agrégateur de news :
    - yfinance (par symboles)
    - + NewsAPI (global business)
    Fusionne, dédoublonne, tronque.
    """
    all_articles: List[Dict[str, Any]] = []
    seen_titles = set()

    # 1) yfinance
    yf_articles = fetch_yfinance_news(max_articles=max_articles * 2)
    for a in yf_articles:
        title = a.get("title")
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        all_articles.append(a)

    # 2) NewsAPI (si dispo)
    api_articles = fetch_newsapi_news(max_articles=max_articles * 2)
    for a in api_articles:
        title = a.get("title")
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        all_articles.append(a)

    return {
        "source": "yfinance+newsapi",
        "fetched_at": time.time(),
        "articles": all_articles[:max_articles],
    }
