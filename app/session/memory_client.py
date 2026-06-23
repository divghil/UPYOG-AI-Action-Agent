import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class RedisAgentMemoryClient:
    def __init__(self, api_url: str, store_id: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.store_id = store_id
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        logger.info(f"Initialized RedisAgentMemoryClient with URL: {self.api_url}, StoreID: {self.store_id}")

    async def add_session_event(self, session_id: str, actor_id: str, role: str, text: str) -> bool:
        """Logs a single conversation event to the session memory cloud."""
        # Sanitize session_id to conform to Redis Memory API regex (only alphanumeric and hyphens)
        sanitized_session_id = session_id.replace("_", "-")
        url = f"{self.api_url}/v1/stores/{self.store_id}/session-memory/events"
        payload = {
            "sessionId": sanitized_session_id,
            "actorId": actor_id,
            "role": role.upper(),
            "content": [{"text": text}],
            "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=self.headers, timeout=10.0)
                if res.status_code in (200, 201):
                    logger.info(f"Successfully recorded session event to Agent Memory Cloud for session: {session_id}")
                    return True
                else:
                    logger.warning(f"Failed to record session event. Code: {res.status_code}, Body: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Error calling Agent Memory add_session_event: {e}")
            return False

    async def create_long_term_memory(self, owner_id: str, memory_id: str, text: str) -> bool:
        """Stores a persistent fact in long-term memory."""
        url = f"{self.api_url}/v1/stores/{self.store_id}/long-term-memory"
        payload = {
            "memories": [
                {
                    "id": memory_id,
                    "ownerId": owner_id,
                    "text": text
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=self.headers, timeout=10.0)
                if res.status_code in (200, 201):
                    logger.info(f"Successfully recorded long term memory item '{memory_id}' for owner: {owner_id}")
                    return True
                else:
                    logger.warning(f"Failed to create long term memory. Code: {res.status_code}, Body: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Error calling Agent Memory create_long_term_memory: {e}")
            return False

    async def search_long_term_memory(self, owner_id: str, query_text: str) -> List[Dict[str, Any]]:
        """Searches long-term memory for semantic facts."""
        url = f"{self.api_url}/v1/stores/{self.store_id}/long-term-memory/search"
        payload = {
            "text": query_text,
            "ownerId": owner_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=self.headers, timeout=10.0)
                if res.status_code == 200:
                    data = res.json()
                    raw_items = data.get("items", [])
                    # Client-side filter to enforce strict tenant separation and prevent memory contamination
                    filtered = [item for item in raw_items if item.get("ownerId") == owner_id]
                    logger.info(f"Retrieved {len(filtered)} long-term memories for owner: {owner_id} (out of {len(raw_items)} total matches)")
                    return filtered
                else:
                    logger.warning(f"Failed to search long-term memory. Code: {res.status_code}, Body: {res.text}")
                    return []
        except Exception as e:
            logger.error(f"Error calling Agent Memory search_long_term_memory: {e}")
            return []
