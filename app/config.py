import os
import logging
from typing import Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    llm_provider: str = "groq"                 # e.g., "groq", "ollama", "openai"
    llm_model: str = Field(
        "llama-3.3-70b-versatile", 
        validation_alias=AliasChoices("LLM_MODEL", "GROQ_MODEL")
    )
    llm_api_key: Optional[str] = Field(
        None, 
        validation_alias=AliasChoices("LLM_API_KEY", "GROQ_API_KEY")
    )
    host: str = "127.0.0.1"
    port: int = 8080
    redis_url: Optional[str] = None
    session_ttl_minutes: int = 30
    api_base: str = "https://niuatt.niua.in"
    use_mock_llm: bool = False
    agent_memory_url: Optional[str] = None
    agent_memory_store_id: Optional[str] = None
    agent_memory_api_key: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

# Helper to load settings with environment variable fallbacks
try:
    settings = Settings()
except Exception as e:
    logger.warning(f"Failed to load settings via BaseSettings: {e}. Trying os.environ fallback.")
    settings = Settings(
        llm_provider=os.environ.get("LLM_PROVIDER", "groq"),
        llm_model=os.environ.get("LLM_MODEL", os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")),
        llm_api_key=os.environ.get("LLM_API_KEY", os.environ.get("GROQ_API_KEY", "mock_key")),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8080")),
        redis_url=os.environ.get("REDIS_URL"),
        session_ttl_minutes=int(os.environ.get("SESSION_TTL_MINUTES", "30")),
        api_base=os.environ.get("API_BASE", "https://niuatt.niua.in"),
        use_mock_llm=os.environ.get("USE_MOCK_LLM", "false").lower() == "true",
        agent_memory_url=os.environ.get("AGENT_MEMORY_URL"),
        agent_memory_store_id=os.environ.get("AGENT_MEMORY_STORE_ID"),
        agent_memory_api_key=os.environ.get("AGENT_MEMORY_API_KEY")
    )
