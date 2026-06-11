"""The seam where the prediction model plugs in.

Steps 3-4 of the plan (the GBDT, then the DNN) will produce a real
``Predictor``. For now ``NullPredictor`` returns nothing, so the board shows
"projection pending" on upcoming games instead of a made-up number.

When the model is ready, implement ``predict`` to return projected runs and
register the predictor in ``create_app`` via the ``PREDICTOR`` config key.
"""
from __future__ import annotations

from typing import Optional, Protocol

from .models import Game


class Predictor(Protocol):
    def predict(self, game: Game) -> Optional[tuple[float, float]]:
        """Return projected (away_runs, home_runs), or None if no projection."""
        ...


class NullPredictor:
    """No-op predictor used until a trained model is wired in."""

    def predict(self, game: Game) -> Optional[tuple[float, float]]:
        return None
