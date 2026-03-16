import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi_utils.tasks import repeat_every   

from .api import health_check, v1_router, RequestIDMiddleware
from .core import (
    settings,
    async_engine,
    setup_logging,
    custom_http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
    get_db_session_cm,
         
)
#from core.database import get_db_session_cm
from .models import Base
from app.services import ResumeService        


@asynccontextmanager
async def lifespan(app: FastAPI):

    # ---- Startup: create DB tables ----
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ---- Initial cleanup at startup ----
    async with get_db_session_cm() as db:
        service = ResumeService(db)
        await service.delete_old_resumes(days_old=7)

    # ---- Periodic cleanup every 24 hours ----
    @repeat_every(seconds=86400)  # 24h
    async def periodic_cleanup():
        async with get_db_session_cm() as db:
            service = ResumeService(db)
            await service.delete_old_resumes(days_old=7)

    app.add_event_handler("startup", periodic_cleanup)

    yield

    # ---- Shutdown ----
    await async_engine.dispose()

def create_app() -> FastAPI:
    """
    configure and create the FastAPI application instance.
    """
    setup_logging()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY, same_site="lax"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    app.add_exception_handler(HTTPException, custom_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    if os.path.exists(settings.FRONTEND_PATH):
        app.mount(
            "/app",
            StaticFiles(directory=settings.FRONTEND_PATH, html=True),
            name=settings.PROJECT_NAME,
        )

    app.include_router(health_check)
    app.include_router(v1_router)

    return app

