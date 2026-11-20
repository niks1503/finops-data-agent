"""Runtime settings, read from environment variables (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("FINOPS_DB", ROOT / "warehouse" / "finops.duckdb"))
    manifest_path: Path = Path(os.getenv("DBT_MANIFEST", ROOT / "dbt" / "target" / "manifest.json"))
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    # Tried in order if the main model is overloaded (503), timing out or rate limited.
    gemini_fallbacks: tuple[str, ...] = tuple(
        m.strip()
        for m in os.getenv(
            "GEMINI_FALLBACK_MODELS", "gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
        ).split(",")
        if m.strip()
    )
    gemini_timeout_s: float = float(os.getenv("GEMINI_TIMEOUT_S", "60"))
    max_steps: int = int(os.getenv("AGENT_MAX_STEPS", "8"))
    max_rows: int = int(os.getenv("AGENT_MAX_ROWS", "200"))
    # Optional prices (USD per 1M tokens) for cost-per-query reporting. 0 on the free tier.
    price_in_per_m: float = float(os.getenv("PRICE_INPUT_PER_M", "0"))
    price_out_per_m: float = float(os.getenv("PRICE_OUTPUT_PER_M", "0"))


settings = Settings()
