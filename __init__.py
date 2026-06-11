"""Application factory.

Configuration is read from the environment so the same code runs locally and
in CI/deploys:

  MLB_BOARD_TZ          display timezone (default America/New_York)
  MLB_BOARD_CACHE_TTL   seconds to cache a schedule response (default 60)
"""
from __future__ import annotations

import logging
import os

from flask import Flask

from .mlb_client import MLBClient
from .predictions import NullPredictor


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config["MLB_TZ"] = os.environ.get("MLB_BOARD_TZ", "America/New_York")
    app.config["CACHE_TTL"] = int(os.environ.get("MLB_BOARD_CACHE_TTL", "60"))
    if config:
        app.config.update(config)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Shared, cached client + the (currently no-op) predictor seam.
    app.config.setdefault("MLB_CLIENT", MLBClient(cache_ttl=app.config["CACHE_TTL"]))
    app.config.setdefault("PREDICTOR", NullPredictor())

    from .views import bp
    app.register_blueprint(bp)
    return app
