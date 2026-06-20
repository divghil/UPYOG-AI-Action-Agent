import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutor
from app.session.store import get_session_store
from app.orchestrator import AgentOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="UPYOG AI Action-Agent Backend Service",
    description="Phase 0 POC - Spec-driven AI Agent orchestrator loop",
    version="0.1.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve directories
current_dir = os.path.dirname(os.path.abspath(__file__))
specs_dir = os.path.join(current_dir, "specs")

# Initialize orchestrator modules
logger.info("Initializing Agent Service components...")

# Dynamic swappable LLM Provider resolution
if settings.use_mock_llm or settings.llm_provider == "mock" or not settings.llm_api_key or settings.llm_api_key in ("mock_key", "your_key_here"):
    from app.llm.mock_provider import MockLLMProvider
    llm_provider = MockLLMProvider()
    logger.info("Using MockLLMProvider for conversation loop (Local Dev/Demo mode).")
elif settings.llm_provider == "groq":
    try:
        from app.llm.groq_provider import GroqProvider
        llm_provider = GroqProvider(api_key=settings.llm_api_key, model=settings.llm_model)
        logger.info(f"Using GroqProvider with model: {settings.llm_model}")
    except Exception as e:
        logger.warning(f"Failed to initialize GroqProvider: {e}. Falling back to MockLLMProvider.")
        from app.llm.mock_provider import MockLLMProvider
        llm_provider = MockLLMProvider()
else:
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

tool_registry = ToolRegistry(specs_dir=specs_dir)
tool_executor = ToolExecutor(api_base=settings.api_base)
session_store = get_session_store(redis_url=settings.redis_url, ttl_minutes=settings.session_ttl_minutes)

orchestrator = AgentOrchestrator(
    llm_provider=llm_provider,
    tool_registry=tool_registry,
    tool_executor=tool_executor
)

# Request/Response schemas
class ChatRequest(BaseModel):
    message: str
    session_id: str
    tenant_id: Optional[str] = "pb.amritsar"

class ChatResponse(BaseModel):
    response: str
    session_id: str
    collected_fields: Dict[str, Any]
    status: str

class ClearRequest(BaseModel):
    session_id: str

@app.get("/")
def health_check():
    return {
        "status": "UP",
        "active_workflow_specs": list(tool_registry.modules.keys()),
        "model": getattr(settings, "llm_model", "mock"),
        "provider": settings.llm_provider,
        "use_mock_llm": settings.use_mock_llm,
        "session_ttl_minutes": settings.session_ttl_minutes
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    """
    Main conversational agent endpoint.
    Retrieves state from store, executes orchestrator loop, and saves updated state.
    Supports citizen authentication via authorization bearer header.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    session_id = request.session_id
    logger.info(f"Incoming request for session: {session_id}")

    try:
        # Load session state (either active or blank new one)
        session_state = await session_store.get(session_id)

        # Autofill tenantId if not already present in collected variables
        if "tenantId" not in session_state.collected_fields:
            session_state.collected_fields["tenantId"] = request.tenant_id or "pb.amritsar"

        # Execute conversation turn
        response_text, status = await orchestrator.run(
            state=session_state,
            user_message=request.message,
            token=token
        )

        # Save state changes
        await session_store.save(session_state)

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            collected_fields=session_state.collected_fields,
            status=status
        )

    except Exception as e:
        logger.error(f"Error handling request in session '{session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/clear")
async def clear_session(request: ClearRequest):
    """Clear memory logs of the specific session ID."""
    try:
        await session_store.clear(request.session_id)
        logger.info(f"Cleared session memory: {request.session_id}")
        return {"status": "SUCCESS", "message": f"Cleared session memory for {request.session_id}"}
    except Exception as e:
        logger.error(f"Error clearing session '{request.session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
