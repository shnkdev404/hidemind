from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SEED_DIR = DATA_DIR / "seed"
SNAPSHOT_DIR = DATA_DIR / "snapshots"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    hindsight_url: str = ""
    hindsight_api_key: str = ""
    bank_id: str = "munshi-ap"

    groq_api_key: str = ""
    agent_model: str = "openai/gpt-oss-120b"

    auto_resolve_max_inr: float = 200_000
    escalate_above_inr: float = 500_000

    sim_concurrency: int = 3
    db_path: Path = DATA_DIR / "munshi.db"

    @property
    def memory_enabled(self) -> bool:
        return bool(self.hindsight_url)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
