from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Eluno OMS"
    app_env: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 1440

    # Database
    database_url: str = "sqlite+aiosqlite:///./eluno_oms.db"

    # Anthropic
    anthropic_api_key: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # SendGrid
    sendgrid_api_key: str = ""
    alert_from_email: str = "oms@eluno.co"

    # SLA (working days)
    sla_single_vision: int = 3
    sla_progressive: int = 7
    sla_bifocal: int = 5
    sla_office: int = 4

    @property
    def sla_map(self) -> dict[str, int]:
        return {
            "Single Vision": self.sla_single_vision,
            "Progressive": self.sla_progressive,
            "Bifocal": self.sla_bifocal,
            "Office": self.sla_office,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()