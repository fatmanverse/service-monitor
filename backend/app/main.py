from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .config import Settings, get_settings
from .database import Database
from .models import User
from .migrations import migrate_database
from .monitoring import MonitoringService
from .routers import (
    agent_commands,
    agents,
    alerts,
    auth,
    hosts,
    resource_groups,
    services,
    users,
)
from .scheduler import MonitorScheduler
from .security import SecretCipher, hash_password


def create_app(settings: Settings = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    database = Database(resolved_settings)
    cipher = SecretCipher(resolved_settings.app_secret)
    monitoring = MonitoringService(cipher, probe_workers=resolved_settings.monitor_workers * 2)
    scheduler = MonitorScheduler(
        database,
        monitoring,
        workers=resolved_settings.monitor_workers,
        agent_offline_seconds=resolved_settings.agent_offline_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        migrate_database(database)
        with database.session_factory() as db:
            admin = db.scalar(
                select(User).where(User.username == resolved_settings.initial_admin_username)
            )
            if not admin:
                db.add(
                    User(
                        username=resolved_settings.initial_admin_username,
                        password_hash=hash_password(resolved_settings.initial_admin_password),
                        is_admin=True,
                        is_active=True,
                    )
                )
            db.commit()
        if resolved_settings.scheduler_enabled:
            scheduler.start()
        yield
        scheduler.shutdown()
        monitoring.shutdown()

    app = FastAPI(
        title="服务监控 API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.cipher = cipher
    app.state.monitoring = monitoring
    app.state.scheduler = scheduler
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/api")
    app.include_router(agent_commands.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(hosts.router, prefix="/api")
    app.include_router(resource_groups.router, prefix="/api")
    app.include_router(services.router, prefix="/api")
    app.include_router(alerts.router, prefix="/api")
    app.include_router(users.router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()
