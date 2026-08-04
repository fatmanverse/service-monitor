import logging
import os
import sys

import uvicorn

from app.agent_grpc_server import create_grpc_server
from app.config import get_settings
from app.main import create_app
from app.migrations import migrate_database


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        print("service-monitor-server self-test ok")
        return 0
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    app = create_app(settings)
    grpc_server = None
    if settings.agent_grpc_enabled:
        migrate_database(app.state.database)
        grpc_server = create_grpc_server(
            app.state.database,
            settings,
            app.state.cipher,
            app.state.monitoring,
        )
        grpc_server.start()
    try:
        uvicorn.run(
            app,
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8000")),
            log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        )
    finally:
        if grpc_server is not None:
            grpc_server.stop(grace=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
