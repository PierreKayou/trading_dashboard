# news/analysis_v2.py

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import json

from openai import OpenAI

from news.router import fetch_raw_news

router = APIRouter(
    prefix="/api/news",  # <--- IMPORTANT : même prefix que le V1
    tags=["news-v2"],
)

client = OpenAI()


# ------------------------------------------------------------------
# Schémas
# ------------------------------------------------------------------


class NewsStressRequest(BaseModel):
    """
    Si articles est fourni, on analyse ceux-ci.
    Sinon, on va chercher les news brutes côté backend (yfinance + NewsAPI).
    """
    max_articles: int = 25
    articles: Optional[List[Dict[str, Any]]] = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _build_neutral_analysis(source: str) -> Dict[str, Any]:
    """
    Analyse neutre si aucun article exploitable.
    """
    return {
        "source": "ia_v2",
        "news_source": source,
        "created_at": time.time(),
        "article_count": 0,
        "articles_used": [],
        "analysis": {
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
            # V2 : bloc spécifique "stress & drivers"
            "stress_signal": {
                "level": "normal",  # low | normal | high
                "label": "Stress de marché normal",
                "comment": (
                    "Faute de news significatives, on considère le niveau de stress "
                    "de marché comme normal / de croisière."
                ),
            },
            "drivers": [],
            "titles_used": [],
        },
    }


def _build_news_block_for_llm(articles: List[Dict[str, Any]]) -> str:
    lines = []
    for art in articles:
        publisher = art.get("publisher") or "?"
        title = art.get("title") or "Sans titre"
        sym = art.get("symbol") or "global"
        lines.append(f"- [{publisher}] ({sym}) {title}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# Endpoint principal V2
# ------------------------------------------------------------------


@router.post("/stress")
def analyze_news_stress(req: NewsStressRequest) -> Dict[str, Any]:
    """
    V2 de l'analyse des news :
    - reprend la structure du /api/news/analyze V1 (macro_sentiment, risk_tone, volatility_outlook, by_asset…)
    - ajoute la notion de "stress_signal" (niveau de stress perçu)
    - ajoute la liste des "drivers" (thèmes / facteurs dominants)
    """

    # 1) Récupération des articles (client ou backend)
    if req.articles:
        articles = req.articles[: req.max_articles]
        source = "client"
    else:
        raw = fetch_raw_news(max_articles=req.max_articles)
        articles = raw.get("articles", []) or []
        source = raw.get("source", "yfinance+newsapi")

    # Si aucune news : analyse neutre
    if not articles:
        return _build_neutral_analysis(source)

    # 2) Construction d'un bloc texte pour l'IA
    news_block = _build_news_block_for_llm(articles)

    # 3) Prompt système + utilisateur
    system_prompt = (
        "Tu es un assistant d'analyse macro-financière pour un trader discrétionnaire.\n"
        "Tu lis des TITRES de news récentes (sans cliquer sur les articles) et tu en tires :\n"
        "- un sentiment macro global (plutôt risk-on, risk-off ou neutre),\n"
        "- une indication de volatilité attendue (élevée, normale, faible),\n"
        "- quelques points clés à retenir (liste brève),\n"
        "- une interprétation synthétique par actif : ES (S&P 500 Futures), "
        "NQ (Nasdaq 100 Futures), BTC (Bitcoin), CL (Crude Oil WTI), GC (Gold).\n"
        "- un signal de STRESS DE MARCHÉ : niveau (low / normal / high) + commentaire.\n"
        "- une liste de 3 à 6 DRIVERS (thèmes) qui expliquent ce stress ou l'absence de stress.\n\n"
        "Tu t'exprimes EN FRANÇAIS.\n"
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
  "stress_signal": {{
    "level": "low | normal | high",
    "label": "Texte court sur le niveau de stress (ex: 'Stress élevé lié au risque géopolitique')",
    "comment": "2-3 phrases max expliquant d'où vient (ou non) le stress."
  }},
  "drivers": [
    {{
      "name": "Nom court du driver (ex: 'Geopolitique', 'Résultats tech', 'Banques centrales')",
      "direction": "risk_on | risk_off | neutral",
      "weight": 0.0,
      "comment": "2-3 phrases max sur l'impact de ce driver."
    }}
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

    # 4) Appel OpenAI
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
        raise HTTPException(status_code=500, detail=f"Erreur OpenAI (V2): {e}")

    content = resp.choices[0].message.content

    try:
        analysis = json.loads(content)
    except Exception:
        # Si jamais le JSON est bancal, on renvoie le texte brut
        analysis = {"raw_text": content}

    # 5) Construction de la réponse finale
    titles_used = [
        art.get("title") for art in articles if art.get("title")
    ]

    # On garde la même enveloppe que le V1 pour que le front réutilise les mêmes champs
    return {
        "source": "ia_v2",
        "news_source": source,
        "created_at": time.time(),
        "article_count": len(articles),
        "articles_used": articles,
        "analysis": {
            **analysis,
            # sécurité : on rajoute les titres utilisés pour affichage éventuel
            "titles_used": titles_used,
        },
    }
