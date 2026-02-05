# news/schemas.py

from pydantic import BaseModel
from typing import Dict, List, Optional


class StressDriver(BaseModel):
    name: str
    weight: float


class AssetStress(BaseModel):
    sensitivity: str  # low | medium | high
    comment: str


class StressResponse(BaseModel):
    stress_score: int                 # 0 → 100
    risk_label: str                   # low_risk | neutral | high_risk
    volatility_regime: str            # low | normal | high
    drivers: Dict[str, float]         # macro_us, macro_eu, geopolitics, crypto...
    by_asset: Dict[str, AssetStress]
    created_at: float
    sources_used: List[str]
