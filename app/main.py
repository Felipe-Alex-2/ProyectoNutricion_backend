from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.config import settings
from app.api.v1.router import api_v1_router
from app.middleware.error_handler import (
    validation_exception_handler,
    general_exception_handler,
)
from app.database import get_engine, Base
import app.models  # Ensure all models are registered with Base


import logging

logger = logging.getLogger("api")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Full-Stack Authentication REST API with FastAPI, PostgreSQL, JWT & bcrypt.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
# Only catch unhandled exceptions in production or non-debug
if settings.ENVIRONMENT != "development_debug":
    app.add_exception_handler(Exception, general_exception_handler)

# Include API Router
app.include_router(api_v1_router, prefix="/api")


@app.get("/", tags=["Health"])
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    from sqlalchemy import text
    from fastapi.responses import JSONResponse
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "ok"}
    except Exception:
        logger.exception("Database readiness check failed")
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})
