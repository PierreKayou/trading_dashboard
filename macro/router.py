# macro/router.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime, date
from openai import OpenAI
import json
import os

router = APIRouter(
    prefix="/macro",
    tags=["macro"],
)

client = OpenAI()

MACRO_MODEL = "gpt-4.1"
MACRO_STATE_FILE = os.path.join(os.getcwd(), "macro_state.json")


class MacroRequest(BaseModel):
    """
    context_text : texte brut / collage de tes sources macro (Fed, CPI, NFP, news, etc.)
    force_refresh : si False, réutilise le macro_state de la semaine en cours s'il existe
    """
    context_text: str
    force_refresh: bool = False


# ======================
# Macro neutre par défaut
# ======================

NEUTRAL_MACRO_STATE: Dict[str, Any] = {
    "timestamp": None,
    "macro_regime": {
        "label": "Neutre",
        "confidence": 0.5,
        "stability": "stable",
    },
    "macro_factors": {
        "monetary_policy": "neutre",
        "inflation_trend": "stable",
        "growth_trend": "stable",
        "risk_sentiment": "neutre",
        "rates_pressure": "neutre",
        "usd_bias": "neutre",
    },
    "market_bias": {
        "equities": "contexte neutre",
        "indices_us": "contexte neutre",
        "commodities": "contexte neutre",
        "crypto": "contexte neutre",
    },
    "invalidations": [],
    "commentary": "Aucun contexte macro explicite disponible, régime neutre par défaut.",
}


# ======================
# Prompts IA
# ======================

MACRO_SYSTEM_PROMPT = """
Tu es une IA spécialisée en analyse macro-économique appliquée aux marchés financiers.

Objectif :
Déterminer le régime macro-économique dominant pour la semaine à venir
(et éventuellement les 2–4 semaines suivantes).

Contraintes :
- Tu ne donnes AUCUN signal de trade.
- Tu ne prédis PAS les prix.
- Tu qualifies uniquement le CONTEXTE MACRO.
- Tu dois répondre STRICTEMENT en JSON valide, sans texte autour.
"""

MACRO_USER_TEMPLATE = """
Voici un résumé (ou collage) des informations macro-économiques récentes :

---
{context_text}
---

À partir de ces informations, produis un objet JSON STRICTEMENT conforme au schéma suivant :

{
  "timestamp": "YYYY-MM-DD",
  "macro_regime": {
    "label": "string (ex: 'Risk-Off Modéré', 'Risk-On', 'Neutre')",
    "confidence": 0.0,
    "stability": "string (ex: 'stable', 'fragile', 'en transition')"
  },
  "macro_factors": {
    "monetary_policy": "restrictive | neutre | accommodante",
    "inflation_trend": "hausse | baisse | stable | désinflation lente",
    "growth_trend": "accélération | ralentissement | stable",
    "risk_sentiment": "risk-on | risk-off | neutre",
    "rates_pressure": "haussière | baissière | neutre",
    "usd_bias": "haussier | baissier | neutre"
  },
  "market_bias": {
    "equities": "string courte (pression baissière, plutôt haussier, range, etc.)",
    "indices_us": "string courte",
    "commodities": "string courte",
    "crypto": "string courte"
  },
  "invalidations": [
    "liste d'événements ou données qui invalideraient ce régime"
  ],
  "commentary": "commentaire synthétique en français sur le contexte macro et la prudence à adopter"
}

Règles :
- Remplis tous les champs.
- Utilise la date du jour pour "timestamp" si l'information n'est pas claire.
- Ne rajoute AUCUN texte en dehors du JSON.
"""


# ======================
# Helpers fichier macro_state
# ======================

def load_macro_state() -> Dict[str, Any]:
    try:
        if os.path.exists(MACRO_STATE_FILE):
            with open(MACRO_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return NEUTRAL_MACRO_STATE


def save_macro_state(state: Dict[str, Any]) -> None:
    try:
        with open(MACRO_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # On loguerait en prod ; ici on balance juste une exception
        raise HTTPException(status_code=500, detail=f"Erreur sauvegarde macro_state.json : {e}")


def same_iso_week(date_str: Optional[str], ref: date) -> bool:
    """
    True si date_str (YYYY-MM-DD) est dans la même semaine ISO que ref.
    """
    if not date_str:
        return False
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False

    year1, week1, _ = d.isocalendar()
    year2, week2, _ = ref.isocalendar()
    return (year1 == year2) and (week1 == week2)


# ======================
# Core IA
# ======================

def generate_macro_state_from_text(context_text: str) -> Dict[str, Any]:
    """
    Appelle le modèle OpenAI pour générer un macro_state structuré JSON
    à partir d'un texte macro.
    """
    user_msg = MACRO_USER_TEMPLATE.format(context_text=context_text)

    resp = client.chat.completions.create(
        model=MACRO_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": MACRO_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )

    content = resp.choices[0].message.content
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Réponse IA invalide (JSON) : {e} | contenu brut : {content[:2000]}",
        )

    # On s'assure qu'il y a un timestamp YYYY-MM-DD
    today_str = date.today().strftime("%Y-%m-%d")
    if "timestamp" not in data or not data["timestamp"]:
        data["timestamp"] = today_str

    return data


# ======================
# ENDPOINTS
# ======================

@router.get("/state")
async def get_state():
    """
    Renvoie le dernier macro_state connu (ou un régime neutre par défaut).
    Utilisé par le /analyze de l'API principale.
    """
    state = load_macro_state()
    return state


@router.post("/generate")
async def generate_macro_state(req: MacroRequest):
    """
    Génère / met à jour le macro_state à partir d'un texte macro.
    - Si un macro_state existe déjà pour la semaine ISO en cours et force_refresh=False,
      on renvoie directement le cache (pas de nouvel appel IA).
    - Sinon, on appelle l'IA, on sauve le nouveau macro_state, et on le renvoie.
    """
    today = date.today()
    current_state = load_macro_state()

    if not req.force_refresh and same_iso_week(current_state.get("timestamp"), today):
        # On considère que le régime hebdo est déjà en place
        return {
            "source": "cache",
            "macro_state": current_state,
        }

    # Sinon : génération IA
    new_state = generate_macro_state_from_text(req.context_text)
    save_macro_state(new_state)

    return {
        "source": "ia",
        "macro_state": new_state,
    }

def generate_macro_state_from_text(context_text: str) -> Dict[str, Any]:
    user_msg = MACRO_USER_TEMPLATE.format(context_text=context_text)

    try:
        resp = client.chat.completions.create(
            model=MACRO_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": MACRO_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
    except Exception as e:
        # On remonte un message clair vers le client
        raise HTTPException(status_code=500, detail=f"Erreur OpenAI: {e}")

    content = resp.choices[0].message.content
    ...
