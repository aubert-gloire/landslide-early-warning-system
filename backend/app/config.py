from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> repo root (two levels up from backend/)
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "landslide_ews"

    # SMS provider: "telerivet" (default) or "africastalking" or "africastalking,telerivet"
    sms_provider: str = "telerivet"

    # Africa's Talking
    at_username: str = "sandbox"
    at_api_key: str = ""
    at_sender_id: str = "LSEWS"

    # Telerivet
    telerivet_api_key: str = ""
    telerivet_project_id: str = ""
    telerivet_route_id: str = ""   # Android SIM route ID — leave blank to use Telerivet default

    # NASA Earthdata (required for GPM IMERG download)
    earthdata_token: str = ""
    earthdata_username: str = ""
    earthdata_password: str = ""

    # OpenTopography
    opentopo_api_key: str = ""

    # GEE
    gee_service_account: str = ""
    gee_key_file: str = "secrets/gee_key.json"

    # App
    app_env: str = "development"
    secret_key: str = "change_me_in_production"
    cors_origin: str = "*"
    officer_password: str = ""

    # Paths (relative to repo root, resolved at runtime)
    data_raw_dir: str = "data/raw"
    data_processed_dir: str = "data/processed"
    data_labels_dir: str = "data/labels"
    ml_artifacts_dir: str = "ml/artifacts"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def raw_path(self) -> Path:
        return REPO_ROOT / self.data_raw_dir

    def processed_path(self) -> Path:
        return REPO_ROOT / self.data_processed_dir

    def labels_path(self) -> Path:
        return REPO_ROOT / self.data_labels_dir

    def artifacts_path(self) -> Path:
        return REPO_ROOT / self.ml_artifacts_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
