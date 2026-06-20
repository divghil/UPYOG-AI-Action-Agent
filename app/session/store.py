import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class SessionState(BaseModel):
    session_id: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    collected_fields: Dict[str, Any] = Field(default_factory=dict)
    active_workflow: Optional[str] = None
    current_step: Optional[str] = None
    pending_mutating_tool: Optional[Dict[str, Any]] = None  # Format: {"name": str, "arguments": dict}
    confirmed_actions: Dict[str, bool] = Field(default_factory=dict)  # Format: {tool_name: is_confirmed}

class SessionStore(ABC):
    @abstractmethod
    async def get(self, session_id: str) -> SessionState:
        """Fetch session state. Return a new blank state if session_id is not found."""
        pass

    @abstractmethod
    async def save(self, state: SessionState) -> None:
        """Persist session state."""
        pass

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """Clear/delete session state."""
        pass

class InMemorySessionStore(SessionStore):
    def __init__(self):
        self._store: Dict[str, str] = {}
        logger.info("Using InMemorySessionStore (fallback).")

    async def get(self, session_id: str) -> SessionState:
        data = self._store.get(session_id)
        if data:
            return SessionState.model_validate_json(data)
        return SessionState(session_id=session_id)

    async def save(self, state: SessionState) -> None:
        self._store[state.session_id] = state.model_dump_json()

    async def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)

class RedisSessionStore(SessionStore):
    def __init__(self, redis_url: str, ttl_seconds: int):
        import redis.asyncio as redis
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl_seconds
        logger.info(f"Using RedisSessionStore pointing to: {redis_url} (TTL = {ttl_seconds} seconds)")

    async def get(self, session_id: str) -> SessionState:
        data = await self.client.get(f"session:{session_id}")
        if data:
            return SessionState.model_validate_json(data)
        return SessionState(session_id=session_id)

    async def save(self, state: SessionState) -> None:
        await self.client.setex(
            f"session:{state.session_id}",
            self.ttl,
            state.model_dump_json()
        )

    async def clear(self, session_id: str) -> None:
        await self.client.delete(f"session:{session_id}")

def get_session_store(redis_url: Optional[str] = None, ttl_minutes: int = 30) -> SessionStore:
    ttl_seconds = ttl_minutes * 60
    if redis_url:
        try:
            import redis
            return RedisSessionStore(redis_url, ttl_seconds)
        except ImportError:
            logger.warning("The 'redis' package is not installed. Falling back to InMemorySessionStore.")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis at {redis_url}: {e}. Falling back to InMemorySessionStore.")
    
    return InMemorySessionStore()
