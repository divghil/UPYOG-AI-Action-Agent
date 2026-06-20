from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]

class LLMResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None

class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        """
        Sends conversation messages to the LLM, optionally providing tool schemas.
        Returns an LLMResponse containing either text response or tool calls.
        """
        pass
