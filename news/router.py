# news/router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import yfinance as yf
import time
import json

from openai import OpenAI

router = APIRouter(prefix="/news", tags=["news"])

# On utilise yfinance comme source de news (Yahoo Finance)
# pour rester simple et éviter une nouvelle API payante.
NEWS_SYMBOLS = [
    "^GSPC",    # S&P 500
    "^NDX",     # Nasdaq 100
    "CL=F",     # Crude Oil Future
    "GC=F",     # Gold Future
    "BTC-USD",  # Bitcoin
]

client = OpenAI()


def fetch_raw_news(max_articles: int = 30) -> Dict[str, Any]:
    """
    Récupère des news récentes via yfinance pour un set d'indices/actifs.
    Retourne un dict normalisé : { source, fetched_at, articles: [...] }.
    """
    all_articles: List[Dict[str, Any]] = []
    seen_titles = set()

    for sym in NEWS_SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            items = ticker.news or []
        except Exception:
            # On ignore les erreurs individuelles
            continue

        for item in items:
            title = item.get("title")
            if not title or title in seen_titles:
                continue

            seen_titles.add(title)
            all_articles.append(
                {
                    "symbol": sym,
                    "title": title,
                    "publisher": item.get("publisher"),
                    "link": item.get("link"),
                    "providerPublishTime": item.get("providerPublishTime"),
                }
            )

    # Tri par date de publication décroissante
    all_articles.sort(
        key=lambda a: a.get("providerPublishTime") or 0,
        reverse=True,
    )

    return {
        "source": "yfinance",
        "fetched_at": time.time(),
        "articles": all_articles[:max_articles],
    }


@router.get("/raw")
def get_raw_news(limit: int = 20) -> Dict[str, Any]:
    """
    Récupération brute des news (liste d'articles) depuis yfinance.
    Utilisable telle quelle par ton dash ou par l'IA.
    """
    if limit <= 0:
        limit = 10
    data = fetch_raw_news(max_articles=limit)
    return data


class NewsAnalyzeRequest(BaseModel):
    """
    Si articles est fourni, on analyse ceux-ci.
    Sinon, on va chercher les news brutes (yfinance) côté backend.
    """
    max_articles: int = 15
    articles: List[Dict[str, Any]] | None = None


@router.post("/analyze")
def analyze_news(req: NewsAnalyzeRequest) -> Dict[str, Any]:
    """
    Prend une liste de news (ou va les chercher tout seul),
    et renvoie une analyse IA structurée :
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
        source = raw.get("source", "yfinance")

    if not articles:
        raise HTTPException(status_code=500, detail="Aucun article disponible pour l'analyse.")

    # 2) Construction d'un résumé texte pour l'IA
    lines = []
    for art in articles:
        publisher = art.get("publisher") or "?"
        title = art.get("title") or "Sans titre"
        sym = art.get("symbol") or "?"
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
        # Si jamais le JSON est mal formé, on renvoie le texte brut
        analysis = {"raw_text": content}

    return {
        "source": "ia",
        "news_source": source,
        "created_at": time.time(),
        "article_count": len(articles),
        "articles_used": articles,
        "analysis": analysis,
    }
