import argparse
import logging
import logging.handlers
import sys

import uvicorn
from dotenv import load_dotenv

from mikoshi.config import AppConfig, LoggingConfig, load_config
from mikoshi.observability import init_observability
from mikoshi.server import app


def configure_logging(cfg: LoggingConfig):
    formatter = logging.Formatter(cfg.format, datefmt=cfg.date_format)

    if cfg.target == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    else:
        # Rotating file handler: 10 MB per file, keep 5 backups
        handler = logging.handlers.RotatingFileHandler(
            cfg.target, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(cfg.level)
    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Override uvicorn loggers to use the same handler and format
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = [handler]
        uvicorn_logger.propagate = False


if __name__ == "__main__":
    load_dotenv(override=True)

    app_config: AppConfig = load_config("config.yaml")
    configure_logging(app_config.logging)
    init_observability(app_config.tracing)
    app.state.app_config = app_config

    uvicorn.run(
        app, host=app_config.server.host, port=app_config.server.port, log_config=None
    )
