from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", frozen=True)

    app_name: str = "House Price Prediction API"
    model_path: Path = Path("models/uci-real-estate-ridge-v1.json")
