from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "SQL Query Generator API"
    app_version: str = "1.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    schema_file: str = "schema.json"
    metadata_file: str = "metadata.json"
    default_dialect: str = "mysql"
    max_limit: int = 10000


settings = Settings()
