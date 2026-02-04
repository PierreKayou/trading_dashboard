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

# CORS large (OK pour Render + front distant)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (si présents)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------
# Pages HTML (front)
# ---------------------------------------------------------

INDEX_FILE = os.path.join(os.getcwd(), "index.html")


@app.get("/", include_in_schema=False)
async def root():
    """
    Sert la page principale du dashboard.
    """
    return FileResponse(INDEX_FILE)


@app.get("/index.html", include_in_schema=False)
async def index_page():
    """
    Alias vers la page principale.
    """
    return FileResponse(INDEX_FILE)


# ---------------------------------------------------------
# API calendrier économique (stub legacy – peut rester)
# ---------------------------------------------------------

class CalendarEvent(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None
    country: Optional[str] = None
    title: str
    impact: Optional[str] = None
    impact_level: Optional[str] = None


class CalendarResponse(BaseModel):
    events: List[CalendarEvent]


@app.get("/api/calendar/today", response_model=CalendarResponse, tags=["calendar"])
async def calendar_today() -> CalendarResponse:
    return CalendarResponse(events=[])


@app.get("/api/calendar/next", response_model=CalendarResponse, tags=["calendar"])
async def calendar_next() -> CalendarResponse:
    return CalendarResponse(events=[])


# ---------------------------------------------------------
# Inclusion des routers métier
# ---------------------------------------------------------

# Flux marché / ticks
app.include_router(ticks_router)

# Paper trading
app.include_router(paper_router, prefix="/paper", tags=["paper"])

# Bots
app.include_router(bots_router, prefix="/bot", tags=["bots"])

# MACRO / NEWS / INDICES / CALENDAR
# 👉 TOUT ce qui est dans macro/router.py est exposé sous /api/...
app.include_router(macro_router, prefix="/api", tags=["macro"])


# ---------------------------------------------------------
# Healthcheck Render
# ---------------------------------------------------------

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
