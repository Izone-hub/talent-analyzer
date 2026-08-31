import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import router
from app.config import INTERNAL_SERVICE_TOKEN
from app.auth import InternalServiceAuthMiddleware, get_internal_token

# Configure logging — never log the token value
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Talent Analyzer",
    description="AI-powered talent analysis service. Internal use only.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — restrict to Backend origin only in production
# ---------------------------------------------------------------------------
if INTERNAL_SERVICE_TOKEN:
    # Production: only allow the Backend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Backend is internal, origination doesn't matter
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Local dev: permissive CORS for easier debugging
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ---------------------------------------------------------------------------
# Internal Service Authentication — protects ALL non-exempt endpoints
# ---------------------------------------------------------------------------
try:
    token = get_internal_token()
    app.add_middleware(InternalServiceAuthMiddleware, token=token)
    logger.info("Internal service authentication: ENABLED")
except ValueError as e:
    logger.warning(
        "INTERNAL_SERVICE_TOKEN not set — running WITHOUT internal auth. "
        "This is insecure and should only be used in local development. "
        f"({e})"
    )

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(router)


@app.get("/health")
async def health():
    """Health check endpoint — no auth required."""
    return {"status": "ok", "service": "talent-analyzer"}
