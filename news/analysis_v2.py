# news/analysis_v2.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import math

from openai import OpenAI

# On réutilise l'agrégateur de news existant
from news.router import fetch_raw_news

router = APIRouter(prefix="/api/news", tags=["news-v2"])

client = OpenAI()

# -------------------------------------------------------------------
# MODELE REQUETE
# -------------------------------------------------------------------


class NewsStressRequest(BaseModel):
    """
    Requête pour l'analyse V2 "stress & drivers".
    max_articles = nombre maximum de titres à survoler.
    """
    max_articles: int = 40


# -------------------------------------------------------------------
# OUTILS "FEATURES" POUR LE PROMPT
# -------------------------------------------------------------------

NEGATIVE_KEYWORDS = [
    "crash",
    "selloff",
    "panic",
    "fear",
    "fears",
    "tension",
    "war",
    "conflict",
    "recession",
    "slowdown",
    "stagflation",
    "default",
    "downgrade",
    "liquidation",
    "shutdown",
    "strike",
    "sanction",
    "geopolitic",
    "geopolitical",
    "uncertainty",
    "uncertainties",
]

POSITIVE_KEYWORDS = [
    "rally",
    "surge",
    "jumps",
    "rebond",
    "bounce",
    "optimism",
    "optimistic",
    "beats",
    "strong",
    "record",
    "soft landing",
    "easing",
    "cooling inflation",
    "relief",
    "stabilize",
    "stabilization",
]


def _score_headline_simple(title: str) -> float:
    """
    Score très simple : +1 si mot positif trouvé, -1 si mot négatif.
    Peut retourner 0 si neutre.
    """
    t = title.lower()
    score = 0.0

    if any(k in t for k in NEGATIVE_KEYWORDS):
        score -= 1.0
    if any(k in t for k in POSITIVE_KEYWORDS):
        score += 1.0

    return score


def _build_features(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Construit quelques features numériques pour guider l'IA :
    - stress_score global
    - ratio headlines négatives / totales
    - ratio headlines positives / totales
    """
    total = len(articles)
    if total == 0:
        return {
            "headline_count": 0,
            "stress_score": 0.0,
            "neg_ratio": 0.0,
            "pos_ratio": 0.0,
        }

    neg = 0
    pos = 0
    agg_score = 0.0

    for a in articles:
        title = (a.get("title") or "").strip()
        if not title:
            continue
        s = _score_headline_simple(title)
        agg_score += s
        if s < 0:
            neg += 1
        elif s > 0:
            pos += 1

    stress_score = 0.0
    if total > 0:
        stress_score = agg_score / math.sqrt(total)

    neg_ratio = neg / total
    pos_ratio = pos / total

    return {
        "headline_count": total,
        "stress_score": stress_score,
        "neg_ratio": neg_ratio,
        "pos_ratio": pos_ratio,
    }


# -------------------------------------------------------------------
# CACHE SIMPLE (EVITE DE SPAM L'API OPENAI)
# -------------------------------------------------------------------

_STRESS_CACHE: Dict[str, Any] = {
    "created_at": None,
    "request_size": None,
    "payload": None,  # ce qui est renvoyé au front
}


def _get_cached_payload(max_articles: int, ttl_seconds: int = 300) -> Optional[Dict[str, Any]]:
    """
    Si on a déjà une analyse récente (< ttl_seconds) avec la même
    taille max_articles, on la renvoie pour éviter de re-payer OpenAI.
    """
    created = _STRESS_CACHE.get("created_at")
    if not created:
        return None

    if _STRESS_CACHE.get("request_size") != max_articles:
        return None

    now = time.time()
    if now - created > ttl_seconds:
        return None

    return _STRESS_CACHE.get("payload")


def _set_cached_payload(max_articles: int, payload: Dict[str, Any]) -> None:
    _STRESS_CACHE["created_at"] = time.time()
    _STRESS_CACHE["request_size"] = max_articles
    _STRESS_CACHE["payload"] = payload


# -------------------------------------------------------------------
# ROUTE PRINCIPALE V2
# -------------------------------------------------------------------


@router.post("/stress")
def news_stress_v2(req: NewsStressRequest) -> Dict[str, Any]:
    """
    Nouvelle analyse IA "News & Stress" (V2).

    - va chercher un flux de news via fetch_raw_news()
    - calcule quelques features de stress basées sur les titres
    - appelle OpenAI avec un prompt structuré
    - renvoie un JSON compatible avec le front :
        {
          "source": "ia_v2",
          "news_source": "...",
          "created_at": ...,
          "article_count": ...,
          "articles_used": [...],
          "analysis": {
             "macro_sentiment": {...},
             "risk_tone": "...",
             "volatility_outlook": "...",
             "key_points": [...],
             "by_asset": {...}
          }
        }
    """

    max_articles = max(5, min(req.max_articles, 80))

    # 1) Essai cache
    cached = _get_cached_payload(max_articles)
    if cached is not None:
        return cached

    # 2) Récupération brute des news
    try:
        raw = fetch_raw_news(max_articles=max_articles * 2)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur récupération news: {e}")

    articles = raw.get("articles", []) or []
    articles = articles[:max_articles]

    source = raw.get("source", "multi")

    if not articles:
        # On renvoie un objet "neutre" (comme dans /analyze V1)
        neutral_analysis = {
            "macro_sentiment": {
                "label": "Neutre",
                "comment": (
                    "Aucune news exploitable remontée par les sources actuelles. "
                    "On considère le contexte informationnel comme neutre."
                ),
            },
            "risk_tone": "neutral",
            "volatility_outlook": "normal",
            "key_points": [
                "Pas de flux de news significatif détecté.",
                "Aucun élément d'information ne vient renforcer ou contredire le biais macro actuel.",
            ],
            "by_asset": {
                "ES": {"bias": "neutral", "comment": "Pas de biais directionnel spécifique pour le S&P 500 à partir des news."},
                "NQ": {"bias": "neutral", "comment": "Pas de signaux clairs sur le Nasdaq dans le flux de news."},
                "BTC": {"bias": "neutral", "comment": "Aucune information saillante concernant Bitcoin."},
                "CL": {"bias": "neutral", "comment": "Pas de catalyseur identifié pour le pétrole WTI."},
                "GC": {"bias": "neutral", "comment": "Pas de news majeures sur l'or à court terme."},
            },
        }

        payload = {
            "source": "ia_v2",
            "news_source": source,
            "created_at": time.time(),
            "article_count": 0,
            "articles_used": [],
            "analysis": neutral_analysis,
        }

        _set_cached_payload(max_articles, payload)
        return payload

    # 3) Construction des features de stress
    features = _build_features(articles)

    # 4) Construction du bloc titres pour le prompt
    # On passe uniquement ce dont l'IA a besoin :
    #   - publisher
    #   - symbole approximatif (ES, NQ, BTC, CL, GC, global)
    #   - titre
    lines: List[str] = []
    slim_articles: List[Dict[str, Any]] = []

    for art in articles:
        publisher = art.get("publisher") or "?"
        title = art.get("title") or "Sans titre"
        sym = art.get("symbol") or "global"

        lines.append(f"- [{publisher}] ({sym}) {title}")

        slim_articles.append(
            {
                "symbol": sym,
                "publisher": publisher,
                "title": title,
            }
        )

    news_block = "\n".join(lines)

    # 5) Prompt OpenAI
    system_prompt = (
        "Tu es un assistant d'analyse macro-financière pour un trader discrétionnaire. "
        "Tu lis UNIQUEMENT des TITRES récents (sans ouvrir les articles) ainsi que quelques "
        "indicateurs simplifiés de stress (ratio de news négatives/positives, score global). "
        "À partir de cela, tu produis une analyse structurée du contexte :\n"
        "- tonalité macro globale (risk-on, risk-off ou neutre),\n"
        "- volatilité attendue (élevée, normale, faible),\n"
        "- quelques points clés à retenir,\n"
        "- un biais par actif : ES (S&P 500 Futures), NQ (Nasdaq 100 Futures), "
        "BTC (Bitcoin), CL (Crude Oil WTI), GC (Gold).\n\n"
        "Tu t'exprimes EN FRANÇAIS. "
        "Tu ne fais pas de prévisions chiffrées précises, seulement des biais qualitatifs. "
        "Réponds STRICTEMENT en JSON, sans texte autour."
    )

    # On injecte les features comme contexte
    features_text = (
        f"Nombre de titres: {features['headline_count']}, "
        f"stress_score (approx): {features['stress_score']:.2f}, "
        f"ratio news négatives: {features['neg_ratio']:.2f}, "
        f"ratio news positives: {features['pos_ratio']:.2f}."
    )

    user_prompt = f"""
Voici une liste de TITRES de news récentes (macro, indices, matières premières, crypto) :

{news_block}

Indicateurs simplifiés de stress sur ces titres :
{features_text}

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
Si tu n'es pas sûr, reste modéré dans tes biais (plutôt neutre).
"""

    # 6) Appel OpenAI
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
        import json

        analysis = json.loads(content)
    except Exception:
        # fallback : on renvoie le texte brut dans un champ raw_text
        analysis = {"raw_text": content}

    payload = {
        "source": "ia_v2",
        "news_source": source,
        "created_at": time.time(),
        "article_count": len(slim_articles),
        "articles_used": slim_articles,
        "analysis": analysis,
    }

    _set_cached_payload(max_articles, payload)
    return payload
