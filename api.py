import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import Base, engine

from ticks.router import router as ticks_router
from paper.router import router as paper_router
from bots.router import router as bots_router
from macro.router import router as macro_router
from news.router import router as news_router
from econ_calendar.router import router as econ_router
from compat.router import router as compat_router


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
    allow_origins=["*"],  # à restreindre si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static (si tu as un dossier /static pour les assets front)
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
# Inclusion des routers fonctionnels
# ---------------------------------------------------------

# Flux de ticks / historique (utilisé par le moteur local & paper)
app.include_router(ticks_router)

# Paper trading (portfolio, positions, historique)
app.include_router(paper_router, prefix="/paper", tags=["paper"])

# Bots & gestion du risque
app.include_router(bots_router, prefix="/bot", tags=["bots"])

# Module macro / news / indicateurs (routes sous /api/...)
app.include_router(macro_router, prefix="/api", tags=["macro"])

# News & sentiment (analyse news IA, flux externe, etc.)
app.include_router(news_router, prefix="/api", tags=["news"])

# Calendrier économique dédié
app.include_router(econ_router, prefix="/api", tags=["calendar"])

# Routes de compatibilité pour l'ancien dashboard
app.include_router(compat_router)


# ---------------------------------------------------------
# Endpoint de santé (optionnel)
# ---------------------------------------------------------

@app.get("/health", tags=["health"])
async def health():
    """
    Simple endpoint de santé pour ping Render / monitoring.
    """
    return {"status": "ok"}
