from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Prep UPSC AI Platform API"
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    turso_database_url: str | None = os.getenv("TURSO_DATABASE_URL")
    turso_auth_token: str | None = os.getenv("TURSO_AUTH_TOKEN")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    jwt_secret: str = os.getenv("JWT_SECRET", "local-dev-secret")
    access_token_expire_seconds: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "86400"))
    scheduler_interval_minutes: int = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "30"))
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    gemini_eval_model: str = os.getenv("GEMINI_EVAL_MODEL", "gemini-1.5-pro")
    gemini_small_model: str = os.getenv("GEMINI_SMALL_MODEL", "gemini-1.5-flash")
    gemini_embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
    allow_demo_ai_fallback: bool = _env_flag("ALLOW_DEMO_AI_FALLBACK", True)
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "1800"))
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "256"))
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    concept_similarity_threshold: float = float(os.getenv("CONCEPT_SIMILARITY_THRESHOLD", "0.76"))
    semantic_point_threshold: float = float(os.getenv("SEMANTIC_POINT_THRESHOLD", "0.74"))
    note_validation_retries: int = int(os.getenv("NOTE_VALIDATION_RETRIES", "2"))
    minimum_static_case_laws: int = int(os.getenv("MINIMUM_STATIC_CASE_LAWS", "2"))
    default_must_weight: float = float(os.getenv("WEIGHT_MUST", "2.0"))
    default_good_weight: float = float(os.getenv("WEIGHT_GOOD", "1.0"))
    default_similarity_weight: float = float(os.getenv("WEIGHT_SIMILARITY", "2.0"))
    default_coverage_weight: float = float(os.getenv("WEIGHT_COVERAGE", "2.0"))
    default_depth_weight: float = float(os.getenv("WEIGHT_DEPTH", "1.5"))
    default_extra_weight: float = float(os.getenv("WEIGHT_EXTRA", "0.5"))
    default_directive_weight: float = float(os.getenv("WEIGHT_DIRECTIVE", "1.0"))
    default_fact_weight: float = float(os.getenv("WEIGHT_FACT", "1.0"))
    default_maturity_weight: float = float(os.getenv("WEIGHT_MATURITY", "1.0"))
    default_impression_weight: float = float(os.getenv("WEIGHT_IMPRESSION", "0.5"))
    db_path: Path = ROOT_DIR / "backend" / "data" / "learning-platform.db"

    @property
    def turso_enabled(self) -> bool:
        return bool(self.turso_database_url and self.turso_auth_token)


settings = Settings()
