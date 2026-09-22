"""Validated configuration shared by services and command-line evaluation."""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / '.env', env_file_encoding='utf-8', extra='ignore',
        env_ignore_empty=True,
    )
    groq_api_key: SecretStr = SecretStr('')
    groq_timeout_seconds: float = Field(default=5, gt=0, le=30)
    crossref_enabled: bool = True
    api_contact_email: str = 'citeguard@example.com'
    crossref_timeout_seconds: float = Field(default=3, gt=0, le=10)
    openalex_enabled: bool = True
    arxiv_enabled: bool = True
    citeguard_mode: Literal['neural', 'baseline'] = 'neural'
    citeguard_allow_download: bool = False


def get_settings() -> Settings:
    return Settings()
