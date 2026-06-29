import json
import logging
from datetime import date
from typing import Dict, Any, Optional, Tuple
from app.llm.base import LLMProvider
from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutor
from app.session.store import SessionState

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(
        self, 
        llm_provider: LLMProvider, 
        tool_registry: ToolRegistry, 
        tool_executor: ToolExecutor,
        memory_client: Optional[Any] = None
    ):
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
        self.memory_client = memory_client

    async def _execute_tool_and_handle_hooks(
        self,
        tool_spec: Any,
        arguments: Dict[str, Any],
        state: SessionState,
        owner_id: str,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        tool_result = await self.tool_executor.execute(
            tool_spec, 
            arguments, 
            state.collected_fields, 
            token
        )
        
        # Post-execution hooks for long-term memory
        if tool_spec.name == "createHallBooking" and tool_result.get("status") == "BOOKING_CREATED":
            try:
                booking_no = tool_result.get("bookingNo")
                applicant = tool_result.get("applicantName") or state.collected_fields.get("applicantName", "Citizen")
                booking_date = tool_result.get("bookingDate") or state.collected_fields.get("bookingStartDate", "")
                hall_code = state.collected_fields.get("communityHallCode", "")
                
                fact_text = f"Citizen {applicant} successfully booked Community Hall {hall_code} (Booking No: {booking_no}) for date {booking_date}."
                logger.info(f"Booking success detected. Creating long-term memory fact: '{fact_text}'")
                
                if self.memory_client:
                    import uuid
                    memory_id = f"booking-{booking_no}"
                    await self.memory_client.create_long_term_memory(
                        owner_id=owner_id,
                        memory_id=memory_id,
                        text=fact_text
                    )
            except Exception as e:
                logger.error(f"Failed to record booking fact in long-term memory: {e}")
                
        return tool_result

    async def run(
        self, 
        state: SessionState, 
        user_message: str, 
        token: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Wrapper to handle session memory logging and execute the turn inner logic.
        """
        # Resolve a stable owner_id for memory across all login methods.
        # Priority: mobileNo (always same for a user, available in every login method)
        #         > userUuid (only available with portal token login, changes per auth)
        #         > token (transient, changes every login session)
        owner_id = (
            state.collected_fields.get("applicantMobileNo") or
            state.collected_fields.get("userUuid") or
            token or
            "citizen-guest"
        )
        
        # 1. Log user message to session memory cloud
        if self.memory_client:
            await self.memory_client.add_session_event(
                session_id=state.session_id,
                actor_id=owner_id,
                role="USER",
                text=user_message
            )
            
        # 2. Execute inner orchestrator logic
        response_text, status = await self._run_inner(state, user_message, owner_id, token)
        
        # 3. Log assistant response to session memory cloud
        if self.memory_client:
            await self.memory_client.add_session_event(
                session_id=state.session_id,
                actor_id=owner_id,
                role="ASSISTANT",
                text=response_text
            )
            
        return response_text, status

    async def _run_inner(
        self, 
        state: SessionState, 
        user_message: str, 
        owner_id: str,
        token: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Runs the core tool-calling and LLM reasoning loop.
        """
        if not state.active_workflow:
            state.active_workflow = "demo"

        workflow_spec = self.tool_registry.get_workflow_spec(state.active_workflow)
        if not workflow_spec:
            logger.error(f"Workflow specification not found for module: {state.active_workflow}")
            return f"Workflow '{state.active_workflow}' is not registered.", "error"

        # 1. Handle Awaiting Confirmation Gate
        if state.pending_mutating_tool:
            clean_msg = user_message.strip().lower()
            pending_tool = state.pending_mutating_tool
            tool_name = pending_tool["name"]
            
            # Split message into words to avoid false positive substring matches (e.g., "y" matching in "my")
            words_in_msg = clean_msg.split()
            
            # Match exact y/n or check if full confirmation words are present
            is_confirmed = (
                clean_msg in ["y", "yes", "confirm", "proceed"] or
                any(word in words_in_msg for word in ["yes", "confirm", "proceed", "haan", "theek"])
            )
            is_rejected = (
                clean_msg in ["n", "no", "cancel", "decline", "nahi", "rehne"] or
                any(word in words_in_msg for word in ["no", "cancel", "decline", "nahi", "rehne"])
            )

            if is_confirmed:
                logger.info(f"User confirmed mutating tool: {tool_name}")
                # Mark as confirmed in session and retrieve specification
                state.confirmed_actions[tool_name] = True
                state.pending_mutating_tool = None
                
                tool_spec, _ = self.tool_registry.get_tool_spec(tool_name)
                if not tool_spec:
                    return f"Error: Tool '{tool_name}' no longer registered.", "error"
                
                # Execute the tool via helper
                tool_result = await self._execute_tool_and_handle_hooks(
                    tool_spec, 
                    pending_tool["arguments"], 
                    state, 
                    owner_id,
                    token
                )
                
                # Append tool call and result to history to resume LLM reasoning
                state.history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": pending_tool["id"],
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(pending_tool["arguments"])
                        }
                    }]
                })
                state.history.append({
                    "role": "tool",
                    "tool_call_id": pending_tool["id"],
                    "name": tool_name,
                    "content": json.dumps(tool_result)
                })
                # Fall through to the LLM loop to formulate response based on tool execution result
            elif is_rejected:
                logger.info(f"User cancelled mutating tool: {tool_name}")
                state.pending_mutating_tool = None
                cancel_text = f"Action cancelled. What would you like to do instead?"
                state.history.append({"role": "user", "content": user_message})
                state.history.append({"role": "assistant", "content": cancel_text})
                return cancel_text, "active"
            else:
                prompt_again = f"I am waiting for your confirmation. Please reply with 'yes' to proceed with the action or 'no' to cancel."
                return prompt_again, "awaiting_confirmation"
        else:
            # Append new user message to conversation history
            state.history.append({"role": "user", "content": user_message})
        
        # Auto-detect tenantId updates from user messages (e.g. "pg.mohali is my city")
        import re
        tenant_match = re.search(r'\b(pg\.\w+|pb\.\w+)\b', user_message.lower())
        if tenant_match:
            new_tenant = tenant_match.group(1)
            old_tenant = state.collected_fields.get("tenantId")
            if new_tenant != old_tenant:
                state.collected_fields["tenantId"] = new_tenant
                logger.info(f"Updated tenantId from '{old_tenant}' to '{new_tenant}' based on user message")

        # 2. Core Tool Loop (Ask LLM -> Execute Non-Mutating Tools -> Repeat)
        loop_count = 0
        max_loops = 5
        
        while loop_count < max_loops:
            loop_count += 1
            
            # Determine the next step in the workflow sequentially
            completed_steps = []
            for step in workflow_spec.steps:
                step_executed = False
                for msg in state.history:
                    if msg.get("role") == "tool" and msg.get("name") == step:
                        try:
                            content = json.loads(msg.get("content", "{}"))
                            if "error" not in content and "Errors" not in content:
                                step_executed = True
                                break
                        except:
                            step_executed = True
                            break
                if step_executed:
                    completed_steps.append(step)
                else:
                    break  # Must complete steps in sequential order

            # Determine the active step we are currently executing
            active_step = None
            for step in workflow_spec.steps:
                if step not in completed_steps:
                    active_step = step
                    break

            # Fetch Groq compatible function schemas restricted to steps up to the active step
            tools_schemas = []
            if active_step:
                try:
                    active_idx = workflow_spec.steps.index(active_step)
                    allowed_tools = workflow_spec.steps[:active_idx + 1]
                except ValueError:
                    allowed_tools = [active_step]
                
                for tool_name in allowed_tools:
                    schema = self.tool_registry.get_tool_schema_for_llm(tool_name)
                    if schema:
                        tools_schemas.append(schema)
            
            # Fetch long-term memory facts for the citizen
            lt_memories_text = ""
            if self.memory_client:
                try:
                    memories = await self.memory_client.search_long_term_memory(
                        owner_id=owner_id,
                        query_text="past community hall bookings, citizen preferences, applicant details"
                    )
                    if memories:
                        lt_memories_text = "\n\nPast Citizen Context & Preferences (Retrieved from Long-Term Memory):\n"
                        for m in memories:
                            lt_memories_text += f"- {m.get('text')}\n"
                except Exception as e:
                    logger.warning(f"Error fetching long-term memory in orchestrator: {e}")

            # Build system prompt injecting workflow rules, gathered fields, and long-term memory context
            today_str = date.today().isoformat()
            system_prompt = (
                f"You are the Upyog AI Action-Agent. Your current goal is: '{workflow_spec.goal}'.\n"
                f"Today's date is: {today_str}.\n\n"
                f"You must guide the user step-by-step through these steps:\n"
                f"{chr(10).join([f'- {step}' for step in workflow_spec.steps])}\n\n"
                f"Current collected variables from the user: {state.collected_fields}"
                f"{lt_memories_text}\n\n"
                f"STRICT RULES:\n"
                f"1. Check if the next step in the workflow requires executing a tool.\n"
                f"2. If all required arguments for a tool are in 'collected variables', call the tool immediately.\n"
                f"3. DO NOT guess, mock, or hallucinate parameter values. If a tool requires arguments that are NOT "
                f"present in the 'collected variables', ask the user to provide them.\n"
                f"4. Once a tool has returned its execution result, explain the outcome to the user and proceed to the next step.\n"
                f"5. If details (such as name, email, or mobile number) are available in the 'Past Citizen Context & Preferences' section, you may pre-fill or suggest them to the user. Ask the user for confirmation (e.g. 'I found your email as CBA@gmail.com, should I use that?') before proceeding to execute a mutating action if any parameter is pre-filled from long-term memory.\n"
                f"6. ALWAYS use the exact dates the user provides. Convert them to YYYY-MM-DD format but NEVER change the year, month, or day. Today's date is {today_str} — use it as a reference for the current year.\n"
                f"7. If a tool call returns an error from the real API, report it to the user honestly and ask them to correct the inputs. Do NOT present mock or fallback data as real results.\n"
            )
            
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(state.history)

            # Get response from the swappable LLM provider
            llm_response = await self.llm_provider.chat(messages, tools=tools_schemas)

            # If LLM triggered a tool call
            if llm_response.tool_calls:
                tc = llm_response.tool_calls[0]
                tool_name = tc.name
                tool_spec, _ = self.tool_registry.get_tool_spec(tool_name)

                if not tool_spec:
                    logger.warning(f"LLM called unregistered tool: {tool_name}")
                    state.history.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tool_name, "arguments": json.dumps(tc.arguments)}
                        }]
                    })
                    state.history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tool_name,
                        "content": json.dumps({"error": f"Tool '{tool_name}' is not registered."})
                    })
                    continue

                # Enforce Confirmation Gate for Mutating actions
                if tool_spec.mutating:
                    is_confirmed = state.confirmed_actions.get(tool_name, False)
                    if not is_confirmed:
                        # Save pending tool call and pause execution to prompt user
                        state.pending_mutating_tool = {
                            "id": tc.id,
                            "name": tool_name,
                            "arguments": tc.arguments
                        }
                        
                        # Format confirmation question based on tool inputs
                        confirm_text = f"Confirm: Do you want to proceed with executing '{tool_name}'? (yes/no)"
                        state.history.append({
                            "role": "assistant",
                            "content": confirm_text
                        })
                        return confirm_text, "awaiting_confirmation"

                # Update collected fields with parsed tool arguments
                state.collected_fields.update(tc.arguments)

                # Execute the tool via helper
                tool_result = await self._execute_tool_and_handle_hooks(
                    tool_spec, 
                    tc.arguments, 
                    state, 
                    owner_id,
                    token
                )

                # Append tool call and result to history
                state.history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": json.dumps(tc.arguments)}
                    }]
                })
                state.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": json.dumps(tool_result)
                })

                # Clear confirmation flag after use
                state.confirmed_actions[tool_name] = False
                
                # Loop back to LLM to formulate response based on tool output
                continue

            else:
                # LLM returned text (e.g., asking user a question or final summary)
                assistant_text = llm_response.text or "I am processing your request."
                state.history.append({"role": "assistant", "content": assistant_text})
                return assistant_text, "active"

        return "Loop execution limit reached without formulating a response.", "error"
