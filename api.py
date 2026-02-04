import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from macro.router import router as macro_router
from news.router import router as news_router
from econ_calendar.router import router as econ_router


# ---------------------------------------------------------
# App & config de base
# ---------------------------------------------------------

app = FastAPI(
    title="Stark Macro Dashboard",
    version="0.1.0",
    description="Backend FastAPI pour le dashboard macro (indices, news, calendrier éco).",
)

# CORS large pour pouvoir appeler l'API depuis n'importe où
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre plus tard si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static (si tu as un dossier /static pour JS / CSS / images)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------
# Pages HTML (front)
# ---------------------------------------------------------

INDEX_FILE = os.path.join(os.getcwd(), "index.html")


@app.get("/", include_in_schema=False)
async def root():
    """
    Sert la page principale du dashboard macro sur "/".
    """
    return FileResponse(INDEX_FILE)


@app.get("/index.html", include_in_schema=False)
async def index_page():
    """
    Alias pour accéder à la même page via /index.html.
    """
    return FileResponse(INDEX_FILE)


@app.get("/macro.html", include_in_schema=False)
async def macro_page():
    """
    Si tu veux une page dédiée macro.html.
    """
    macro_file = os.path.join(os.getcwd(), "macro.html")
    if os.path.isfile(macro_file):
        return FileResponse(macro_file)
    # fallback sur index si macro.html n'existe pas
    return FileResponse(INDEX_FILE)


# ---------------------------------------------------------
# Inclusion des routers fonctionnels
# ---------------------------------------------------------
# ⚠️ IMPORTANT :
# - On NE fait PLUS d'import de `database`, `ticks`, `paper` ou `bots` ici.
# - Ce service Render est dédié à : macro + news + calendrier économique.

# Module macro (inclut /api/macro/snapshot, /api/macro/orientation, etc.)
app.include_router(macro_router, prefix="/api", tags=["macro"])

# Module news (analyse de news, sentiment, etc.)
app.include_router(news_router, prefix="/api", tags=["news"])

# Module calendrier économique (source dédiée)
app.include_router(econ_router, prefix="/api", tags=["calendar"])


# ---------------------------------------------------------
# Endpoint de santé (Render healthcheck)
# ---------------------------------------------------------

@app.get("/health", tags=["health"])
async def health():
    """
    Simple endpoint de santé pour Render / monitoring.
    """
    return {"status": "ok"}
