import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Routers "macro only"
from macro.router import router as macro_router
from news.router import router as news_router
from econ_calendar.router import router as econ_router
from compat.router import router as compat_router


# ---------------------------------------------------------
# App & config de base
# ---------------------------------------------------------

app = FastAPI(
    title="Stark Trading Dashboard – Macro",
    version="0.1.0",
    description="Backend FastAPI Render pour le dashboard macro (indices, news, calendrier).",
)

# CORS large pour pouvoir appeler l'API depuis ton front où qu'il soit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre plus tard si besoin
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
# Inclusion des routers fonctionnels (MACRO ONLY)
# ---------------------------------------------------------

# Module macro / indicateurs (snapshot, indices, biais, calendar macro, etc.)
app.include_router(macro_router, prefix="/api", tags=["macro"])

# News & Sentiment (analyse news IA, flux externe)
app.include_router(news_router, prefix="/api", tags=["news"])

# Calendrier économique dédié
app.include_router(econ_router, prefix="/api", tags=["calendar"])

# Routes de compatibilité pour l'ancien dashboard (latest, perf/summary, macro/state, etc.)
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
