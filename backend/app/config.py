"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_name: str = "Prism"
    secret_key: str = "change-me-in-production"
    # Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@db:5432/prism
    database_url: str = "postgresql+asyncpg://prism:prism@localhost:5432/prism"
    data_dir: str = "./data"
    # Disable connection pooling (used by the test suite, which runs each test on
    # its own event loop and must not reuse asyncpg connections across loops).
    db_disable_pool: bool = False
    # Public base URL of the deployment; used to build OIDC redirect URLs.
    public_url: str = "http://localhost:8000"
    tz: str = "UTC"

    # Auth / cookies
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = False  # set true behind HTTPS
    cookie_domain: str | None = None
    # When true, anyone can self-register a local account. When false, only SSO/invites.
    allow_registration: bool = True

    # Authentik / OIDC (optional). When oidc_enabled is false, only local auth is used.
    oidc_enabled: bool = False
    oidc_issuer: str | None = None  # e.g. https://authentik.example.com/application/o/prism/
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_scopes: str = "openid email profile"
    oidc_display_name: str = "Authentik"
    # Members of this Authentik group are granted Prism admin.
    oidc_admin_group: str | None = None

    # Nextcloud (contact source of truth + calendar target). For the initial
    # release these are instance-level service credentials backing a shared
    # address book; per-user account linking is a planned enhancement.
    nextcloud_url: str | None = None
    nextcloud_username: str | None = None
    nextcloud_app_password: str | None = None
    nextcloud_addressbook: str = "contacts"
    nextcloud_calendar: str = "personal"
    sync_interval_minutes: int = 15

    # Weather enrichment (Open-Meteo, no API key required).
    weather_enabled: bool = True

    # Background scheduler (periodic sync + reminder dispatch). Disabled in tests.
    scheduler_enabled: bool = True

    @property
    def oidc_redirect_url(self) -> str:
        return f"{self.public_url.rstrip('/')}/api/auth/oidc/callback"

    @property
    def oidc_metadata_url(self) -> str | None:
        """OIDC discovery URL. Accepts either the issuer or the full
        .well-known/openid-configuration URL in OIDC_ISSUER."""
        if not self.oidc_issuer:
            return None
        base = self.oidc_issuer.rstrip("/")
        suffix = "/.well-known/openid-configuration"
        if base.endswith(suffix.lstrip("/")):
            return base
        return f"{base}{suffix}"

    @property
    def nextcloud_configured(self) -> bool:
        return bool(self.nextcloud_url and self.nextcloud_username and self.nextcloud_app_password)

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
