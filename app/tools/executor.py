import time
import logging
import random
from typing import Dict, Any, Optional
from app.tools.base import ToolSpec

logger = logging.getLogger(__name__)

class ToolExecutor:
    def __init__(self, api_base: str):
        self.api_base = api_base

    async def execute(
        self, 
        tool_spec: ToolSpec, 
        inputs: Dict[str, Any], 
        session_fields: Dict[str, Any], 
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a tool call according to its specification.
        Injects session parameters (like tenantId) and citizen token,
        performs audit logging, and handles local mock results for Phase 0/1.
        """
        # 1. Resolve inputs: autofill from session variables if source == session
        resolved_params = {}
        for param_name, input_spec in tool_spec.inputs.items():
            if input_spec.source == "session":
                resolved_params[param_name] = session_fields.get(param_name, "pb.amritsar")
            else:
                resolved_params[param_name] = inputs.get(param_name)

        # 2. Audit Logging
        logger.info(
            f"[AUDIT] [TOOL_EXECUTION] "
            f"UserTokenLength={len(token) if token else 0} | "
            f"Tool='{tool_spec.name}' | "
            f"Params={resolved_params} | "
            f"Mutating={tool_spec.mutating}"
        )

        # 3. Dynamic Mock Routing
        if tool_spec.name == "getDemoStatus":
            return {
                "status": "ACTIVE",
                "message": f"Hello {resolved_params.get('userName', 'Guest')}! The Upyog AI Agent POC is running successfully.",
                "tenantId": resolved_params.get("tenantId"),
                "active_modules": [
                    "CHB (Community Hall Booking) - Phase 0 Mock",
                    "ADS (Advertisement Booking) - Planned"
                ],
                "timestamp": str(time.time())
            }

        elif tool_spec.name == "triggerFakeBooking":
            return {
                "bookingId": f"DEMO-BOOK-{int(time.time())}",
                "status": "CONFIRMED",
                "demoId": resolved_params.get("demoId"),
                "tenantId": resolved_params.get("tenantId"),
                "message": "This is a mock booking confirmation. No actual resources were reserved."
            }

        # Real/Mock Community Hall Booking (CHB) Service integrations
        elif tool_spec.name == "searchCommunityHallSlots":
            return {
                "communityHallCode": resolved_params.get("communityHallCode"),
                "hallCode": resolved_params.get("hallCode"),
                "slots": [
                    {
                        "date": resolved_params.get("bookingStartDate"),
                        "slotStatus": "AVAILABLE",
                        "timeSlot": "09:00 AM - 09:00 PM"
                    }
                ],
                "message": "The queried slot is available."
            }

        elif tool_spec.name == "createHallBooking":
            booking_id = f"CHB-BOOK-{random.randint(100000, 999999)}"
            return {
                "bookingNo": booking_id,
                "status": "BOOKING_CREATED",
                "applicantName": resolved_params.get("applicantName"),
                "bookingDate": resolved_params.get("bookingStartDate"),
                "message": f"Community hall booking created successfully. Reference ID: {booking_id}."
            }

        # Generic mock fallback
        return {
            "status": "MOCK_SUCCESS",
            "tool": tool_spec.name,
            "resolved_params": resolved_params,
            "message": "Executed successfully (mock)."
        }
