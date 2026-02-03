import os
import datetime as dt
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import Base, engine
from ticks.router import router as ticks_router
from paper.router import router as paper_router
from bots.router import router as bots_router
from macro.router import router as macro_router


# ---------------------------------------------------------
# App & config de base
# ---------------------------------------------------------

app = FastAPI(
    title="Stark Trading Dashboard",
    version="0.1.0",
    description="Backend FastAPI pour le dashboard trading + macro.",
)

# Création des tables SQLAlchemy
Base.metadata.create_all(bind=engine)

# CORS large pour pouvoir appeler l'API depuis n'importe où
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre si tu veux
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static (optionnel : si tu as un dossier /static pour des assets)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------
# Pages HTML (front)
# ---------------------------------------------------------

INDEX_FILE = os.path.join(os.getcwd(), "index.html")


@app.get("/", include_in_schema=False)
async def root():
    """
    Sert la page principale du dashboard (macro + trading) sur "/".
    """
    return FileResponse(INDEX_FILE)


@app.get("/index.html", include_in_schema=False)
async def index_page():
    """
    Alias pour accéder à la même page via /index.html.
    """
    return FileResponse(INDEX_FILE)


# ---------------------------------------------------------
# API calendrier économique (simple stub pour le moment)
# ---------------------------------------------------------

class CalendarEvent(BaseModel):
    date: Optional[str] = None   # "2026-02-03"
    time: Optional[str] = None   # "14:30"
    country: Optional[str] = None  # "US", "EU", "FR", etc.
    title: str                   # Nom de l'événement
    impact: Optional[str] = None        # "high" / "medium" / "low"
    impact_level: Optional[str] = None  # idem, doublon pour le front


class CalendarResponse(BaseModel):
    events: List[CalendarEvent]


@app.get("/api/calendar/today", response_model=CalendarResponse, tags=["calendar"])
async def calendar_today() -> CalendarResponse:
    """
    Calendrier économique du jour (UTC).

    Pour l'instant, renvoie une liste vide.
    Tu pourras brancher une vraie source (Forexfactory, etc.)
    en remplissant la liste events.
    """
    today = dt.date.today().isoformat()
    return CalendarResponse(
        events=[
            # Exemple de structure si tu veux tester l'affichage :
            # CalendarEvent(
            #     date=today,
            #     time="14:30",
            #     country="US",
            #     title="NFP (emplois non agricoles)",
            #     impact="high",
            #     impact_level="high",
            # )
        ]
    )


@app.get("/api/calendar/next", response_model=CalendarResponse, tags=["calendar"])
async def calendar_next() -> CalendarResponse:
    """
    Calendrier économique des prochains jours.

    Idem, pour l'instant renvoie une liste vide.
    """
    # Exemple si tu veux un prochain événement :
    # tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    return CalendarResponse(events=[])


# ---------------------------------------------------------
# Inclusion des routers fonctionnels
# ---------------------------------------------------------

# Flux de ticks / historique (utilisé par le moteur local & paper)
app.include_router(ticks_router)

# Paper trading (portfolio, positions, historique)
app.include_router(paper_router, prefix="/paper", tags=["paper"])

# Bots & gestion du risque
app.include_router(bots_router, prefix="/bot", tags=["bots"])

# Module macro / news / indicateurs (toutes les routes sous /api/...)
#   - /api/macro/week/raw
#   - /api/week/summary       (ou /api/macro/week/summary, selon ton router)
#   - /api/macro              (biais global)
#   - /api/news/analyze       (analyse news IA)
app.include_router(macro_router, prefix="/api")


# ---------------------------------------------------------
# Endpoint de santé (optionnel)
# ---------------------------------------------------------

@app.get("/health", tags=["health"])
async def health():
    """
    Simple endpoint de santé pour ping Render / monitoring.
    """
    return {"status": "ok"}
