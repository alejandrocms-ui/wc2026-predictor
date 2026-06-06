"""Central configuration via pydantic-settings.

All knobs come from environment variables / ``.env`` (see ``.env.example``). No secrets
are ever hardcoded. The app is designed to run with *zero* keys (Tier-0); every API key
field defaults to empty and downstream adapters degrade gracefully when one is absent.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = parent of the ``wc2026`` package dir.
_REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings. Instantiate via :func:`get_settings` (cached)."""

    model_config = SettingsConfigDict(
        env_prefix="WC2026_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    data_dir: Path = Field(default=_REPO_ROOT / "data")
    lang: str = Field(default="es", description="Default UI language: es | en")
    random_seed: int = Field(default=20260611, description="Seed for reproducible sims")
    n_simulations: int = Field(default=50_000, ge=1)
    decay_halflife_days: float = Field(default=547.0, gt=0)
    offline: bool = Field(default=False, description="Never hit the network if true")

    # --- Tier-1 (free, optional) ---
    football_data_token: str = Field(default="")

    # --- Tier-2 (paid, optional) ---
    api_football_key: str = Field(default="")

    # --- LLM (optional, cosmetic explanation only — NOT a data source) ---
    deepseek_api_key: str = Field(default="")

    # --- Derived paths ---
    @property
    def seed_dir(self) -> Path:
        return self.data_dir / "seed"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "wc2026.duckdb"

    def ensure_dirs(self) -> None:
        """Create the data directories if missing (idempotent)."""
        for d in (self.data_dir, self.seed_dir, self.cache_dir):
            d.mkdir(parents=True, exist_ok=True)

    # --- Capability flags (drives the data-tier badge in the UI) ---
    @property
    def has_tier1(self) -> bool:
        return bool(self.football_data_token)

    @property
    def has_tier2(self) -> bool:
        return bool(self.api_football_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()


# Repo root re-exported for modules that need to locate committed seed files.
REPO_ROOT = _REPO_ROOT
