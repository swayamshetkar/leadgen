from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.database.connection import init_db
from app.discovery.browser.playwright_manager import PlaywrightManager
from app.api.discovery import router as discovery_router

setup_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Lead Discovery Engine database schema...")
    await init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down Lead Discovery Engine services...")
    pw_manager = await PlaywrightManager.get_instance()
    await pw_manager.shutdown()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Free Multi-Source Lead Discovery Engine",
    description=(
        "A standalone, 100% free, multi-source lead discovery and web intelligence engine. "
        "Discovers relevant, unique, evidence-backed businesses using public search engines, "
        "local POI directories, social profile indexers, website intelligence, and structured extraction."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(discovery_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "Lead Discovery Engine",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=(settings.ENVIRONMENT == "development")
    )
