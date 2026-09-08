import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPERIS_", env_file=".env", extra="ignore")
    environment: Literal["development", "production", "test"] = "development"
    app_origin: str = "http://localhost:5173"
    supabase_url: str = ""
    supabase_publishable_key: SecretStr = SecretStr("")
    session_seconds: int = 3600
    discovery_ingest_key: SecretStr = SecretStr("")
    discovery_browser_targets: dict[str, dict] = {}

    @model_validator(mode="after")
    def validate_production(self):
        from .browser_discovery import valid_target

        for tenant, target in self.discovery_browser_targets.items():
            UUID(tenant)
            if not isinstance(target.get("base_url"), str):
                raise ValueError("Configure a fixed Epicor application URL")
            valid_target(target["base_url"])
            if (
                not isinstance(target.get("companies"), list)
                or not target["companies"]
                or any(
                    not isinstance(c, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", c)
                    for c in target["companies"]
                )
            ):
                raise ValueError("Configure explicit Epicor company codes")
        origin = urlparse(self.app_origin)
        if not origin.netloc or origin.path not in ("", "/") or origin.query or origin.fragment:
            raise ValueError("APP_ORIGIN must be an origin without a path")
        if not 60 <= self.session_seconds <= 3600:
            raise ValueError("SESSION_SECONDS must be between 60 and 3600")
        if self.environment == "production":
            if origin.scheme != "https" or not self.supabase_url.startswith("https://"):
                raise ValueError("Production requires HTTPS origins and Supabase")
            if not self.configured:
                raise ValueError("Production requires Supabase configuration")
        return self

    @property
    def configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key.get_secret_value())

    @property
    def cookie_name(self) -> str:
        return "__Host-operis_session" if self.environment == "production" else "operis_session"


@lru_cache
def get_settings() -> Settings:
    return Settings()
