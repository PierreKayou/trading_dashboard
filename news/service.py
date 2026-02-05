# news/service.py

from typing import List, Dict, Any
import time
import os
import yfinance as yf
import httpx

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"

NEWS_SYMBOLS = [
    "^GSPC",    # S&P 500
    "^NDX",     # Nasdaq 100
    "CL=F",     # Crude Oil
    "GC=F",     # Gold
    "BTC-USD",  # Bitcoin
]


def fetch_yfinance_news(max_articles: int = 30) -> List[Dict[str, Any]]:
    articles = []
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
    if not NEWS_API_KEY:
        return []

    params = {
        "category": "business",
        "language": "en",
        "pageSize": max_articles,
    }

    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                NEWS_API_URL,
                params=params,
                headers={"X-Api-Key": NEWS_API_KEY},
            )
    except Exception:
        return []

    if resp.status_code != 200:
        return []

    data = resp.json()
    articles = []

    for art in data.get("articles", []):
        if not art.get("title"):
            continue

        articles.append(
            {
                "symbol": "global",
                "title": art["title"],
                "publisher": art.get("source", {}).get("name"),
                "link": art.get("url"),
                "providerPublishTime": None,
            }
        )

    return articles


def fetch_raw_news(max_articles: int = 30) -> Dict[str, Any]:
    all_articles = []
    seen_titles = set()

    for src in (
        fetch_yfinance_news(max_articles * 2),
        fetch_newsapi_news(max_articles * 2),
    ):
        for art in src:
            title = art.get("title")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            all_articles.append(art)

    return {
        "source": "yfinance+newsapi",
        "fetched_at": time.time(),
        "articles": all_articles[:max_articles],
    }
