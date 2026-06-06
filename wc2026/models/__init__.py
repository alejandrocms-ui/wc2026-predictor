"""Predictive models: Dixon-Coles (primary), GBM (tertiary), ensemble, calibration.

Every model exposes the same contract: ``predict_match(home, away, context) ->
ScorelineMatrix``, from which all derived markets (1X2 / BTTS / O-U / exact score) follow.
"""

from .scoreline import ScorelineMatrix

__all__ = ["ScorelineMatrix"]
