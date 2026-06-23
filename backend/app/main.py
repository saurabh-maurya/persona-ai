from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import get_settings
from app.database import get_db, close_db, init_indexes
from app.logging_config import configure_logging, get_logger
from app.api import characters, batches, dashboard, auth
from app.dependencies import require_auth

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(debug=settings.debug)
    app.state.db = get_db()
    await init_indexes()
    logger.info("startup", app=settings.app_name, version=settings.app_version)
    yield
    await close_db()
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(characters.router, prefix="/api", dependencies=[Depends(require_auth)])
    app.include_router(batches.router, prefix="/api", dependencies=[Depends(require_auth)])
    app.include_router(dashboard.router, prefix="/api", dependencies=[Depends(require_auth)])

    @app.get("/api/health")
    async def health():
        if settings.gemini_api_key:
            ai_provider = "gemini"
            ai_model = settings.gemini_model
        elif settings.groq_api_key:
            ai_provider = "groq"
            ai_model = settings.groq_model
        else:
            ai_provider = "none"
            ai_model = ""
        return {
            "status": "ok",
            "version": settings.app_version,
            "ai_provider": ai_provider,
            "ai_model": ai_model,
        }

    frontend_path = Path(__file__).parent.parent.parent / "frontend"
    if frontend_path.exists():
        app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

    return app


app = create_app()
