"""
Configuration module for RankPulse.
Defines paths, rolling window parameters, threshold guards, and runtime settings.
"""

from __future__ import annotations
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "rankpulse"
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = DATA_DIR / "rankpulse.db"

# Model artifact path
MODEL_PATH = MODELS_DIR / "momentum_model.joblib"
METADATA_PATH = MODELS_DIR / "model_metadata.json"

# Operational Parameters
LOOKBACK_DAYS: int = 14       # Current observation period (P1)
PREV_LOOKBACK_DAYS: int = 14  # Preceding baseline period (P0) for momentum calculation
FORWARD_DAYS: int = 14        # Future period (P2) used for labeling/evaluation
MIN_IMPRESSIONS_FLOOR: int = 100  # Minimum impressions in P1 to filter noise
DECLINE_THRESHOLD: float = 0.20   # 20% drop threshold: imp_p2 < 0.80 * imp_p1

# API & Server Settings
API_HOST: str = os.environ.get("RANKPULSE_HOST", "127.0.0.1")
API_PORT: int = int(os.environ.get("RANKPULSE_PORT", "8000"))
DEBUG: bool = os.environ.get("RANKPULSE_DEBUG", "False").lower() in ("true", "1")
