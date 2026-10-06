from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings.

    Real environment variables win over the project-root ``.env`` file. The ``.env`` path is
    anchored to this file, so it is found no matter which directory the server or tests run from.
    """

    DATABASE_URL: str = "postgresql+psycopg2://kyc_user:kyc_password@127.0.0.1:5433/kyc_db"

    # Relative paths are resolved against backend/ (never against the process working directory).
    STORAGE_DIR: str = "../storage"

    # Automatic tries per step. MAX_RETRIES is the default; the per-step values override it
    # (docs: face = 3, liveness = 3).
    MAX_RETRIES: int = 3
    FACE_MAX_RETRIES: Optional[int] = None
    LIVENESS_MAX_RETRIES: Optional[int] = None

    # Server-side sanity checks on the results the browser reports.
    FACE_MIN_QUALITY: float = 0.5
    LIVENESS_MIN_SCORE: float = 0.5

    # Largest accepted recording upload.
    MAX_UPLOAD_BYTES: int = 500 * 1024 * 1024

    # Comma-separated browser origins allowed to call the API directly (the Vite dev proxy does not need this).
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore", env_ignore_empty=True)

    @property
    def storage_root(self) -> Path:
        path = Path(self.STORAGE_DIR)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path.resolve()

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def max_retries_for(self, step: str) -> int:
        override = {"FACE": self.FACE_MAX_RETRIES, "LIVENESS": self.LIVENESS_MAX_RETRIES}.get(step)
        return override if override is not None else self.MAX_RETRIES


settings = Settings()
