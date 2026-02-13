from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from app.config import settings
from app.database import init_db
from app.api.v1 import sources, health, test_scraping, process, scheduler, articles, stocks, database, config


# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Stock News API...")
    logger.info(f"Initializing database at {settings.DATABASE_URL}")
    init_db()
    logger.info("Database initialized successfully")

    # Initialize and start scheduler
    from app.scheduler import scheduler_service
    logger.info("Initializing scheduler...")
    scheduler_service.initialize()
    scheduler_service.start()
    logger.info("Scheduler started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Stock News API...")
    logger.info("Stopping scheduler...")
    scheduler_service.shutdown()
    logger.info("Scheduler stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered stock news aggregation and analysis API",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
app.include_router(articles.router, prefix="/api/v1")
app.include_router(stocks.router, prefix="/api/v1")
app.include_router(database.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(test_scraping.router, prefix="/api/v1")
app.include_router(process.router, prefix="/api/v1")
app.include_router(scheduler.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
