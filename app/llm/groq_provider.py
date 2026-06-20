import json
import logging
from typing import List, Dict, Any, Optional
from groq import AsyncGroq
from app.llm.base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.client = AsyncGroq(api_key=self.api_key)

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        logger.info(f"Calling Groq: model={self.model}, messages_count={len(messages)}, tools_count={len(tools) if tools else 0}")
        
        # Prepare API arguments
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1
        }
        
        if tools and len(tools) > 0:
            params["tools"] = tools
            params["tool_choice"] = "auto"
            
        try:
            response = await self.client.chat.completions.create(**params)
            choice = response.choices[0]
            message = choice.message
            
            text = message.content
            tool_calls = None
            
            if message.tool_calls:
                tool_calls = []
                for tc in message.tool_calls:
                    try:
                        arguments = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception as e:
                        logger.error(f"Failed to parse arguments JSON: {tc.function.arguments}, error: {e}")
                        arguments = {}
                    
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments
                    ))
                    
            return LLMResponse(text=text, tool_calls=tool_calls)
            
        except Exception as e:
            logger.error(f"Groq API invocation error: {e}")
            raise e
