# news/router.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import os
import time
import json

import yfinance as yf
import httpx
from openai import OpenAI

# IMPORTANT : plus de "/api" ici, on laisse juste "/news"
router = APIRouter(prefix="/news", tags=["news"])

# ------------------------------------------------------------------
# CONFIG : NewsAPI (https://newsapi.org) pour compléter yfinance
# ------------------------------------------------------------------
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"

client = OpenAI()

# ... (le reste du fichier inchangé)

client = OpenAI()

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


@router.get("/raw")
def get_raw_news(limit: int = 20) -> Dict[str, Any]:
    """
    Récupération brute des news (liste d'articles) depuis yfinance + NewsAPI.
    """
    if limit <= 0:
        limit = 10
    data = fetch_raw_news(max_articles=limit)
    return data


class NewsAnalyzeRequest(BaseModel):
    """
    Si articles est fourni, on analyse ceux-ci.
    Sinon, on va chercher les news brutes côté backend.
    """
    max_articles: int = 15
    articles: List[Dict[str, Any]] | None = None


@router.post("/analyze")
def analyze_news(req: NewsAnalyzeRequest) -> Dict[str, Any]:
    """
    Analyse IA structurée du flux de news :
    - sentiment macro global
    - tonalité risk-on / risk-off
    - volatilité attendue
    - points clés
    - impacts par actif (ES, NQ, BTC, CL, GC)
    """
    # 1) Récup des articles
    if req.articles:
        articles = req.articles[: req.max_articles]
        source = "client"
    else:
        raw = fetch_raw_news(max_articles=req.max_articles)
        articles = raw.get("articles", [])
        source = raw.get("source", "yfinance+newsapi")

    # Si aucune news : analyse neutre
    if not articles:
        neutral_analysis = {
            "macro_sentiment": {
                "label": "Neutre",
                "comment": (
                    "Aucune news exploitable remontée par les sources actuelles. "
                    "On considère le contexte informationnel comme neutre par défaut."
                ),
            },
            "risk_tone": "neutral",
            "volatility_outlook": "normal",
            "key_points": [
                "Pas de news macro/financières majeures détectées via les sources configurées.",
                "Le flux d'information ne remet pas en cause le biais technique ou macro en place.",
                "Rester attentif à l'agenda économique et aux prochaines publications.",
            ],
            "by_asset": {
                "ES": {
                    "bias": "neutral",
                    "comment": (
                        "Sans news particulières, aucun biais directionnel spécifique "
                        "lié au flux d'information pour l'ES."
                    ),
                },
                "NQ": {
                    "bias": "neutral",
                    "comment": "Pas de news marquantes orientant clairement le Nasdaq à court terme.",
                },
                "BTC": {
                    "bias": "neutral",
                    "comment": "Aucune information spécifique ne modifie le biais de fond sur Bitcoin.",
                },
                "CL": {
                    "bias": "neutral",
                    "comment": (
                        "Pas de catalyseur d'actualité identifié sur le pétrole WTI via les sources utilisées."
                    ),
                },
                "GC": {
                    "bias": "neutral",
                    "comment": "Sans news majeures, l'or conserve un rôle neutre dans le contexte actuel.",
                },
            },
        }

        return {
            "source": "ia",
            "news_source": source,
            "created_at": time.time(),
            "article_count": 0,
            "articles_used": [],
            "analysis": neutral_analysis,
        }

    # 2) Construction d'un résumé texte pour l'IA
    lines = []
    for art in articles:
        publisher = art.get("publisher") or "?"
        title = art.get("title") or "Sans titre"
        sym = art.get("symbol") or "global"
        lines.append(f"- [{publisher}] ({sym}) {title}")

    news_block = "\n".join(lines)

    # 3) Appel OpenAI pour interprétation macro + par actif
    system_prompt = (
        "Tu es un assistant d'analyse macro-financière pour un trader discrétionnaire. "
        "Tu lis des TITRES de news récentes (sans cliquer sur les articles) et tu en tires :\n"
        "- un sentiment macro global (plutôt risk-on, risk-off ou neutre),\n"
        "- une indication de volatilité attendue (élevée, normale, faible),\n"
        "- quelques points clés à retenir (liste brève),\n"
        "- une interprétation synthétique par actif : ES (S&P 500 Futures), "
        "NQ (Nasdaq 100 Futures), BTC (Bitcoin), CL (Crude Oil WTI), GC (Gold).\n\n"
        "Tu t'exprimes EN FRANÇAIS. "
        "Réponds STRICTEMENT en JSON, sans texte autour."
    )

    user_prompt = f"""
Voici une liste de TITRES de news récentes (macro, indices, matières premières, crypto) :

{news_block}

Produit une sortie JSON avec la structure suivante :

{{
  "macro_sentiment": {{
    "label": "Risk-Off Modéré | Neutre | Risk-On", 
    "comment": "Texte court expliquant le ton global des news."
  }},
  "risk_tone": "risk_off | risk_on | neutral",
  "volatility_outlook": "high | normal | low",
  "key_points": [
    "Puces courtes (3 à 6) avec les faits ou thèmes majeurs."
  ],
  "by_asset": {{
    "ES": {{
      "bias": "bullish | bearish | neutral",
      "comment": "2-3 phrases max sur l'impact probable sur ES."
    }},
    "NQ": {{
      "bias": "bullish | bearish | neutral",
      "comment": "2-3 phrases max sur NQ."
    }},
    "BTC": {{
      "bias": "bullish | bearish | neutral",
      "comment": "Impact probable sur Bitcoin."
    }},
    "CL": {{
      "bias": "bullish | bearish | neutral",
      "comment": "Impact probable sur le pétrole WTI."
    }},
    "GC": {{
      "bias": "bullish | bearish | neutral",
      "comment": "Impact probable sur l'or."
    }}
  }}
}}

Respecte cette structure au maximum.
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
        raise HTTPException(status_code=500, detail=f"Erreur OpenAI: {e}")

    content = resp.choices[0].message.content
    try:
        analysis = json.loads(content)
    except Exception:
        analysis = {"raw_text": content}

    return {
        "source": "ia",
        "news_source": source,
        "created_at": time.time(),
        "article_count": len(articles),
        "articles_used": articles,
        "analysis": analysis,
    }
