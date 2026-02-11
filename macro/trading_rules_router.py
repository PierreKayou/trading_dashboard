###############################
# macro/trading_rules_router.py
###############################
from __future__ import annotations

from datetime import datetime, date
from typing import List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

# Ce router sera monté sous /api/macro via api.py
router = APIRouter(prefix="/macro", tags=["macro_trading_rules"])


# ======================================================
# Schémas envoyés au moteur local
# ======================================================

RiskMode = Literal["risk_on", "risk_off", "neutral"]
VolRegime = Literal["low", "normal", "high"]
Bias = Literal["bullish", "bearish", "neutral"]
Impact = Literal["low", "medium", "high"]


class MacroTradingGlobalRules(BaseModel):
    """
    Règles globales applicables à tout le portefeuille.

    - risk_mode: "risk_on" | "risk_off" | "neutral"
    - volatility_regime: "low" | "normal" | "high"
    - allow_new_positions: est-ce qu'on autorise l'ouverture de nouvelles positions ?
    - max_risk_per_trade_factor: multiplicateur à appliquer au risque standard (1.0 = normal)
    """

    generated_for_date: date
    risk_mode: RiskMode
    volatility_regime: VolRegime = "normal"
    allow_new_positions: bool = True
    max_risk_per_trade_factor: float = 1.0
    comment: Optional[str] = None


class MacroTradingMarketRule(BaseModel):
    """
    Règles spécifiques à un marché / symbole donné.

    C'est là qu'on dit par exemple :
    - "éviter ES avant 14h45"
    - "focus NQ aujourd'hui"
    - "CL : seulement gestion de position"
    """

    symbol: str
    bias: Bias = "neutral"
    priority: int = 1  # 0 = à éviter, 3 = focus
    allow_new_positions: bool = True
    only_manage_existing: bool = False
    max_position_factor: float = 1.0
    block_until: Optional[datetime] = None
    notes: Optional[str] = None


class MacroTradingEventRule(BaseModel):
    """
    Fenêtre de non-trade autour d'un évènement macro
    (CPI, NFP, FOMC, stocks pétrole, etc.).
    """

    label: str
    time_utc: datetime
    impact: Impact
    affected_symbols: List[str]
    no_trade_before_minutes: int = 0
    no_trade_after_minutes: int = 0


class MacroTradingRules(BaseModel):
    """
    Paquet complet envoyé au moteur de trading local.

    C'est typiquement ce JSON que tes bots viendront lire pour adapter :
    - les tailles de position
    - l'ouverture / blocage de nouveaux trades
    - les marchés à privilégier ou à éviter
    """

    generated_at: datetime
    version: str = "macro_rules_v1"
    global_rules: MacroTradingGlobalRules
    markets: List[MacroTradingMarketRule]
    events: List[MacroTradingEventRule] = []


# ======================================================
# V1 : stub simple (structure OK, logique à affiner)
# ======================================================

@router.get("/trading_rules", response_model=MacroTradingRules)
async def get_macro_trading_rules() -> MacroTradingRules:
    """
    V1 : on renvoie un paquet de règles statique / simple, pour valider
    la forme du message consommé par le moteur local.

    Ensuite on branchera :
    - la vue indices (/api/macro/indices)
    - l'analyse news IA (/api/news/stress ou /api/news/analyze_v2)
    - le calendrier éco (/api/macro/calendar ou /api/econ/calendar)
    pour rendre ces règles dynamiques.
    """

    now = datetime.utcnow()
    today = now.date()

    # ---------------------------
    # Règles globales (stub)
    # ---------------------------
    global_rules = MacroTradingGlobalRules(
        generated_for_date=today,
        risk_mode="neutral",
        volatility_regime="normal",
        allow_new_positions=True,
        max_risk_per_trade_factor=1.0,
        comment=(
            "V1 stub : environnement neutre. "
            "Les règles seront affinées plus tard en fonction des indices, news IA et calendrier."
        ),
    )

    # ---------------------------
    # Règles par marché (stub)
    # ---------------------------
    # On pose une base pour tes marchés principaux ; plus tard on ajustera
    # bias / priority / block_until en fonction des vraies données.
    markets: List[MacroTradingMarketRule] = [
        MacroTradingMarketRule(
            symbol="ES",
            bias="neutral",
            priority=2,
            allow_new_positions=True,
            only_manage_existing=False,
            max_position_factor=1.0,
            notes="S&P 500 Future : marché principal, autorisé en taille standard.",
        ),
        MacroTradingMarketRule(
            symbol="NQ",
            bias="neutral",
            priority=2,
            allow_new_positions=True,
            only_manage_existing=False,
            max_position_factor=1.0,
            notes="Nasdaq 100 Future : autorisé en taille standard.",
        ),
        MacroTradingMarketRule(
            symbol="BTC",
            bias="neutral",
            priority=1,
            allow_new_positions=True,
            only_manage_existing=False,
            max_position_factor=0.8,
            notes="Bitcoin : autorisé mais taille un peu réduite par défaut.",
        ),
        MacroTradingMarketRule(
            symbol="CL",
            bias="neutral",
            priority=1,
            allow_new_positions=True,
            only_manage_existing=False,
            max_position_factor=0.8,
            notes="Crude Oil : autorisé, taille réduite.",
        ),
        MacroTradingMarketRule(
            symbol="GC",
            bias="neutral",
            priority=1,
            allow_new_positions=True,
            only_manage_existing=False,
            max_position_factor=0.8,
            notes="Gold : autorisé, taille réduite.",
        ),
    ]

    # ---------------------------
    # Evènements macro (stub vide V1)
    # ---------------------------
    events: List[MacroTradingEventRule] = []
    # Plus tard : on peuplerait ça à partir du calendrier éco :
    # - CPI, NFP, FOMC, stocks pétrole, etc.
    # - no_trade_before_minutes / no_trade_after_minutes
    # - affected_symbols = ["ES", "NQ", "CL", "GC", "BTC"] selon le cas

    rules = MacroTradingRules(
        generated_at=now,
        version="macro_rules_v1",
        global_rules=global_rules,
        markets=markets,
        events=events,
    )
    return rules
