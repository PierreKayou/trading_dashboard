# news/router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import time
import os
import json
import requests
import feedparser

from openai import OpenAI

router = APIRouter(prefix="/api/news", tags=["news"])
client = OpenAI()

# ======================================================
# SOURCES GRATUITES – PRIORITÉ PROP FIRM
# ======================================================

RSS_SOURCES = {
    "reuters": "https://feeds.reuters.com/reuters/businessNews",
    "wsj": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "ft": "https://www.ft.com/?format=rss",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories",
    "coindesk": "https://feeds.feedburner.com/CoinDesk",
}

MAX_ARTICLES_DEFAULT = 25

# ======================================================
# MODELS
# ======================================================

class NewsAnalyzeRequest(BaseModel):
    max_articles: int = MAX_ARTICLES_DEFAULT

# ======================================================
# FETCH RSS
# ======================================================

def fetch_rss_news(max_articles: int) -> List[Dict[str, Any]]:
    articles = []
    seen = set()

    for source, url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        for entry in feed.entries:
            title = entry.get("title")
            if not title or title in seen:
                continue

            seen.add(title)

            articles.append({
                "source": source,
                "title": title,
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "link": entry.get("link"),
            })

            if len(articles) >= max_articles:
                return articles

    return articles[:max_articles]

# ======================================================
# IA ANALYSE V2
# ======================================================

@router.post("/analyze-v2")
def analyze_news_v2(req: NewsAnalyzeRequest):
    articles = fetch_rss_news(req.max_articles)

    if not articles:
        return {
            "source": "rss",
            "created_at": time.time(),
            "article_count": 0,
            "analysis": {
                "macro_sentiment": {
                    "label": "Neutre",
                    "comment": "Aucune news exploitable disponible via les sources gratuites."
                },
                "risk_tone": "neutral",
                "volatility_outlook": "normal",
                "key_points": [],
                "by_asset": {}
            }
        }

    # Construction prompt
    lines = []
    for a in articles:
        lines.append(f"- [{a['source']}] {a['title']}")

    news_block = "\n".join(lines)

    system_prompt = (
        "Tu es un analyste macro-financier professionnel spécialisé prop-firm.\n"
        "Tu analyses uniquement des TITRES de news (pas les articles complets).\n"
        "Objectif : aider un trader futures / indices / crypto à comprendre le CONTEXTE.\n"
        "Réponds STRICTEMENT en JSON."
    )

    user_prompt = f"""
Voici des TITRES de news récentes :

{news_block}

Structure JSON OBLIGATOIRE :

{{
  "macro_sentiment": {{
    "label": "Risk-On | Risk-Off | Neutre",
    "comment": "Synthèse macro claire (2-3 phrases)"
  }},
  "risk_tone": "risk_on | risk_off | neutral",
  "volatility_outlook": "high | normal | low",
  "key_points": [
    "3 à 6 points clés factuels"
  ],
  "by_asset": {{
    "ES": {{ "bias": "bullish | bearish | neutral", "comment": "Impact S&P500" }},
    "NQ": {{ "bias": "bullish | bearish | neutral", "comment": "Impact Nasdaq" }},
    "BTC": {{ "bias": "bullish | bearish | neutral", "comment": "Impact Bitcoin" }},
    "CL": {{ "bias": "bullish | bearish | neutral", "comment": "Impact pétrole" }},
    "GC": {{ "bias": "bullish | bearish | neutral", "comment": "Impact or" }}
  }}
}}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        analysis = json.loads(resp.choices[0].message.content)
    except Exception:
        analysis = {"error": "Invalid IA response"}

    return {
        "source": "rss",
        "created_at": time.time(),
        "article_count": len(articles),
        "analysis": analysis,
    }
