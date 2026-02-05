# news/service.py

from typing import List, Dict, Any, Optional
import time
import datetime as dt


def fetch_raw_news(
    symbols: Optional[List[str]] = None,
    max_articles: int = 50,
    days_back: int = 7,
) -> List[Dict[str, Any]]:
    """
    Stub de compatibilité pour macro.service.

    macro/service.py importe cette fonction pour construire la vue hebdo
    (build_week_raw / build_week_summary).

    Pour l'instant, on renvoie une liste vide, ce qui signifie :
    - pas de news brutes exploitées pour la grille hebdo
    - mais l'import existe, donc l'appli démarre correctement

    TODO (plus tard) :
    - brancher ici la vraie récupération de news (mêmes sources que la V2 /api/news/stress)
    - renvoyer une liste d'articles au format standardisé :
      [
        {
          "symbol": "ES",
          "published_at": "2026-02-05T12:34:00Z",
          "title": "Titre de la news",
          "source": "yfinance+newsapi",
          "url": "https://…",
          "raw": {...}  # payload brut si besoin
        },
        ...
      ]
    """

    # On retourne une liste vide pour ne pas casser les agrégations
    # dans macro/service.py (for article in fetch_raw_news(...): ...)
    return []
