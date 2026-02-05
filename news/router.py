# news/router.py

from fastapi import APIRouter
from news.service import build_stress_report
from news.schemas import StressResponse

router = APIRouter(prefix="/api/news", tags=["news"])


@router.post("/stress", response_model=StressResponse)
def get_news_stress():
    """
    Stress macro & news IA – V2

    Objectif :
    - mesurer le niveau de stress global
    - identifier les drivers dominants
    - donner une lecture par actif (prop-firm compliant)
    """
    return build_stress_report()
