# news/router.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
import time
import json

from openai import OpenAI

from news.service import fetch_raw_news

router = APIRouter(prefix="/api/news", tags=["news"])

client = OpenAI()


class NewsAnalyzeRequest(BaseModel):
    """
    Si articles est fourni, on analyse ceux-ci.
    Sinon, on va chercher les news brutes côté backend.
    """
    max_articles: int = 15
    articles: List[Dict[str, Any]] | None = None


def _neutral_analysis(source: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyse neutre de secours (utilisée si OpenAI ou les flux cassent)
    """
    return {
        "source": "ia",
        "news_source": source,
        "created_at": time.time(),
        "article_count": len(articles),
        "articles_used": articles,
        "analysis": {
            "macro_sentiment": {
                "label": "Neutre",
                "comment": (
                    "Le flux d'actualités ne permet pas de dégager de biais clair. "
                    "On considère le contexte global comme neutre."
                ),
            },
            "risk_tone": "neutral",
            "volatility_outlook": "normal",
            "key_points": [
                "Pas de thématique dominante ressortant nettement des titres analysés.",
                "Le flux d'information ne remet pas en cause le biais technique ou macro en place.",
                "Rester attentif à l'agenda économique et aux prochaines publications.",
            ],
            "by_asset": {
                "ES": {
                    "bias": "neutral",
                    "comment": (
                        "Sans signal clair dans les news, aucun biais directionnel "
                        "spécifique lié au flux d'information pour l'ES."
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
        },
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


@router.post("/analyze")
def analyze_news(req: NewsAnalyzeRequest) -> Dict[str, Any]:
    """
    Analyse IA structurée du flux de news :
    - sentiment macro global
    - tonalité risk-on / risk-off
    - volatilité attendue
    - points clés
    - impacts par actif (ES, NQ, BTC, CL, GC)

    ⚠️ En cas d'erreur OpenAI ou de flux, on renvoie une analyse NEUTRE
    plutôt qu'une erreur HTTP 500, pour éviter un bloc vide sur le front.
    """
    # 1) Récup des articles
    if req.articles:
        articles = req.articles[: req.max_articles]
        source = "client"
    else:
        try:
            raw = fetch_raw_news(max_articles=req.max_articles)
        except Exception:
            # si yfinance/NewsAPI cassent → neutre
            return _neutral_analysis("sources_indisponibles", [])

        articles = raw.get("articles", [])
        source = raw.get("source", "yfinance+newsapi")

    # Si aucune news : analyse neutre
    if not articles:
        return _neutral_analysis(source, [])

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

    except Exception:
        # Si OpenAI casse → analyse neutre
        return _neutral_analysis(f"{source}+openai_error", articles)
