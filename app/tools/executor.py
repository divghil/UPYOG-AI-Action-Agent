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

        # Real Community Hall Booking (CHB) Service integration - Slot Search
        elif tool_spec.name == "searchCommunityHallSlots":
            import httpx
            url = f"{self.api_base}/chb-services/booking/v1/_slot-search"
            
            # Build userInfo dict from session fields if available for proper auth
            user_info = None
            user_uuid = session_fields.get("userUuid")
            if user_uuid:
                user_info = {
                    "id": 0,
                    "uuid": user_uuid,
                    "userName": session_fields.get("applicantMobileNo", ""),
                    "name": session_fields.get("applicantName", ""),
                    "mobileNumber": session_fields.get("applicantMobileNo", ""),
                    "emailId": session_fields.get("applicantEmailId", ""),
                    "type": "CITIZEN",
                    "roles": [{"name": "Citizen", "code": "CITIZEN", "tenantId": session_fields.get("tenantId", "pg")}],
                    "active": True,
                    "tenantId": session_fields.get("tenantId", "pg")
                }
            
            # Construct standard UPYOG RequestInfo using the incoming token
            request_info = {
                "apiId": "Rainmaker",
                "ver": ".01",
                "ts": "",
                "action": "_search",
                "did": "1",
                "key": "",
                "authToken": token or "",
                "msgId": f"{int(time.time() * 1000)}|en_IN",
                "plainAccessRequest": {}
            }
            if user_info:
                request_info["userInfo"] = user_info
            
            # RequestInfoWrapper JSON body
            body = {
                "RequestInfo": request_info
            }
            
            # Query parameters (bound via @ModelAttribute in the controller)
            # Map frontend names (communityHallCode, hallCode) to real backend properties (venueCode, unitCode)
            # Use the LATEST tenantId from session_fields (user may have updated it mid-conversation)
            tenant_id = session_fields.get("tenantId", resolved_params.get("tenantId", "pg.citya"))
            params = {
                "tenantId": tenant_id,
                "venueCode": resolved_params.get("communityHallCode") or resolved_params.get("venueCode"),
                "unitCode": resolved_params.get("hallCode") or resolved_params.get("unitCode"),
                "bookingStartDate": resolved_params.get("bookingStartDate"),
                "bookingEndDate": resolved_params.get("bookingEndDate")
            }
            
            try:
                logger.info(f"Calling real slot-search API: {url} with params {params}")
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=body, params=params, timeout=20.0)
                    response.raise_for_status()
                    result = response.json()
                    logger.info(f"Slot search API response: {result}")
                    return result
            except Exception as e:
                error_body = ""
                if isinstance(e, httpx.HTTPStatusError):
                    try:
                        error_body = e.response.text
                    except Exception:
                        pass
                logger.warning(f"Error calling real searchCommunityHallSlots API ({e} - {error_body}). Falling back to mock slots.")
                # Fallback mock slots to prevent blocking the flow
                return {
                    "slots": [
                        {
                            "slotId": "SLOT-1",
                            "slotTime": "06:00-17:59",
                            "status": "AVAILABLE",
                            "date": params.get("bookingStartDate")
                        }
                    ],
                    "message": "Slots retrieved successfully (Mock Fallback)."
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
