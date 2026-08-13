from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        extra="ignore",
    )

    # WhatsApp / Evolution API
    authentication_api_key: str
    evo_base_url: str
    evo_instance_name: str

    # Application database (PostGIS). Separate from the Evolution API database.
    conectese_database_url: str = (
        "postgresql+asyncpg://conectese:conectese@localhost:5434/conectese"
    )

    # LLM. Empty is tolerated so the ETL and the transit endpoints can run
    # without an OpenAI account; the agent raises a clear error if it is unset.
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    # Routing / ETA
    google_maps_api_key: str = ""

    # RUMO (Grande Recife) data source
    rumo_base_url: str = "https://virtual.granderecife.pe.gov.br/rumo"
    rumo_max_concurrency: int = 4
    rumo_timeout_seconds: float = 30.0
    # Politeness pacing; see RumoClient. Raise it if RUMO starts timing out.
    rumo_request_delay_seconds: float = 0.15

    # MCP servers config file (optional). When absent, no external tools are loaded.
    mcp_config_path: Path = BASE_DIR / "mcp_servers.json"

    @property
    def sync_database_url(self) -> str:
        """psycopg3 (sync) DSN, used by Alembic and the LangGraph checkpointer."""
        return self.conectese_database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        )


settings = Settings()
