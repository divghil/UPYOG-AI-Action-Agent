# UPYOG AI Action-Agent Service (Phase 1 POC)

This is the Python-based Agent Service backend representing the active integration of **Redis Agent Memory** and **Real UPYOG API Services**.

It demonstrates:
1. **Generic Spec-Driven Tool Registry**: Loads YAML configurations (`app/specs/*.yaml`) and exposes tool schemas to the LLM dynamically. Supports the sequential `chb` (Community Hall Booking) and `demo` workflows.
2. **Generic Orchestrator Loop**: Implements the tool execution loop with no hardcoded business logic.
3. **Safety confirmation gate**: Intercepts mutating actions (such as `createHallBooking`) and pauses execution to ask the user for explicit confirmation.
4. **Session State Memory**: Stores chat logs, collected parameters, and state details in Redis (with automatic in-memory fallback for local dev).
5. **Two-Tier Long-Term Memory (LTM)**:
   * **Short-Term Session Memory**: Conversation events and active workflow variables stored in Redis with an auto-expiring TTL.
   * **Long-Term Persistent Memory**: Connects to the Redis Agent Memory Cloud to store citizen preferences, booking references, and profile facts across sessions.
   * **Auto-Summarized Fact Retrieval**: Leverages background task summarizations, utilizing an expanded search limit (`limit: 100`) and a secure client-side isolation filter (matching both direct `ownerId` and embedded identifiers inside `session_id`) to prevent cross-citizen memory contamination.
6. **Portal Auth & Live API Integration**:
   * Communicates with the live UPYOG backend (e.g. `/chb-services/booking/v1/_slot-search`).
   * Wraps requests in the standard UPYOG `RequestInfo` structure containing the citizen's `authToken` and dynamic `userInfo` JSON (UUID, mobile, name, email, roles, tenantId) mapped from active session variables.
7. **Swappable LLMProvider**: Abstracted model interface (defaults to Groq using `llama-3.3-70b-versatile`).

---

## 1. Setup Instructions

### Step 1: Install Dependencies
Open your shell, navigate to the `ai-agent` directory, create a virtual environment, and install the dependencies:
```bash
python -m venv venv
.\venv\Scripts\activate      # On Windows
source venv/bin/activate    # On Unix/macOS
python -m pip install -r requirements.txt
```

### Step 2: Configure Environment
Configure your `.env` file with the following variables:
*   `GROQ_API_KEY`: Your Groq API key.
*   `GROQ_MODEL=llama-3.3-70b-versatile`
*   `HOST=127.0.0.1`
*   `PORT=8080`
*   `REDIS_URL`: Supply your local or cloud Redis connection string (e.g. `redis://default:password@host:port`) for session state caching, or leave blank to fall back to `InMemorySessionStore`.
*   `SESSION_TTL_MINUTES=180`
*   `API_BASE=https://niuatt.niua.in`: Base URL pointing to the live UPYOG backend.
*   `AGENT_MEMORY_URL`: The Redis Agent Memory Cloud endpoint URL.
*   `AGENT_MEMORY_STORE_ID`: The unique store ID for the Agent Memory Cloud.
*   `AGENT_MEMORY_API_KEY`: The authorization API key for the Agent Memory Cloud.

### Step 3: Run the Server
Start the Uvicorn server:
```bash
.\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

---

## 2. Active Workflows

### 1. Community Hall Booking (CHB)
Located in `app/specs/chb.yaml`, this workflow guides the user step-by-step to:
1.  **Search Available Slots** (`searchCommunityHallSlots`): Calls the live UPYOG slot search API. Mapped to backend parameters (`venueCode`, `unitCode`, dates, tenantId) and verified with the citizen's auth credentials. 
2.  **Submit Booking Application** (`createHallBooking`): Mutating action that triggers the confirmation gate before generating a mock successful application ID.

### 2. Demo Workflow
Located in `app/specs/demo.yaml`, this workflow is used to test and verify the action-agent loop:
1.  **Get Demo Status** (`getDemoStatus`): Retrieves the current system status and active modules.
2.  **Trigger Test Booking** (`triggerFakeBooking`): Mutating action requiring user confirmation.

---

## 3. LTM Autocomplete & Guided Prefilling
To bypass strict constraints against LLM hallucinations, the orchestrator prompt enforces **Rule 5**:
> *If profile details or preferences (such as name, email, or mobile number) are available in the 'Past Citizen Context & Preferences' section, you may pre-fill or suggest them to the user. Ask the user for confirmation (e.g. 'I found your email as CBA@gmail.com, should I use that?') before proceeding to execute a mutating action if any parameter is pre-filled from long-term memory.*

This allows the agent to automatically retrieve your saved details from previous sessions and suggest them during active booking workflows.

---

## 4. API Endpoints & Testing

### Health Check
*   **URL:** `GET http://127.0.0.1:8080/`
*   **Response:**
    ```json
    {
      "status": "UP",
      "active_workflow_specs": ["chb", "demo"],
      "model": "llama-3.3-70b-versatile",
      "session_ttl_minutes": 180
    }
    ```

### Chat Execution Loop (`/chat`)
This endpoint accepts requests and handles the tool execution loop. Pass the citizen's authentication token in the request header (`Authorization: Bearer <token>`) or inside the request JSON body (`"token": "<token>"`).

*   **Request JSON Payload Structure:**
    ```json
    {
      "message": "list my previous booking details",
      "session_id": "user-9876543210-wbg9fqq",
      "token": "9876543210"
    }
    ```
