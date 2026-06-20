import logging
from typing import List, Dict, Any, Optional
from app.llm.base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

class MockLLMProvider(LLMProvider):
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        logger.info("[MOCK LLM] Simulating LLM reasoning turn...")

        if not messages:
            return LLMResponse(text="Hello! I am the Upyog AI Action-Agent. How can I help you?")

        # Look at the very last message in the history list to determine the turn type
        last_msg = messages[-1]
        role = last_msg.get("role")

        # CASE A: A tool has just executed, so formulate a text summary of the result
        if role == "tool":
            tool_name = last_msg.get("name")
            tool_result_str = last_msg.get("content", "{}")
            logger.info(f"[MOCK LLM] Formulating text response for tool: {tool_name}")
            
            if tool_name == "getDemoStatus":
                return LLMResponse(
                    text="The Upyog AI Agent POC status is ACTIVE. The mock Community Hall Booking is active, and Advertisement Booking is planned."
                )
            elif tool_name == "triggerFakeBooking":
                return LLMResponse(
                    text="Your test booking has been successfully confirmed. No actual resources have been reserved."
                )

        # CASE B: The user has just sent a message, so decide whether to trigger a tool call
        elif role == "user":
            content = last_msg.get("content", "")
            logger.info(f"[MOCK LLM] Processing user message: '{content}'")

            # Check if user asks for status/verification
            if any(word in content.lower() for word in ["status", "verify", "check"]):
                return LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="call_mock_status_123",
                            name="getDemoStatus",
                            arguments={"userName": "CitizenA"}
                        )
                    ]
                )

            # Check if user asks for booking/reservation
            if any(word in content.lower() for word in ["book", "reserve", "trigger"]):
                return LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="call_mock_book_456",
                            name="triggerFakeBooking",
                            arguments={"demoId": "DEV-99"}
                        )
                    ]
                )

        # Default fallback text
        return LLMResponse(
            text="Hello! I am the Upyog AI Action-Agent. I can help verify system status or trigger a demo booking. What would you like to do?"
        )
