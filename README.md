# UPYOG AI Action-Agent Service (Phase 0 POC)

This is the Python-based Agent Service backend representing **Phase 0 (Skeleton)** of the Upyog AI Action-Agent.

It demonstrates:
1. **Generic Spec-Driven Tool Registry**: Loads YAML configurations (`app/specs/*.yaml`) and exposes tool schemas to the LLM dynamically.
2. **Generic Orchestrator Loop**: Implements the tool execution loop with no hardcoded business logic.
3. **Safety confirmation gate**: Intercepts mutating actions and pauses execution to ask the user for explicit confirmation.
4. **Session State Memory**: Stores chat logs, collected parameters, and state details in Redis (with automatic in-memory fallback for local dev).
5. **Swappable LLMProvider**: Abstracted model interface (defaults to Groq).

---

## 1. Setup Instructions

The service is pre-configured to use the existing Groq API key and supports Redis-based Agent Memory Cloud.

### Step 1: Install Dependencies
Open your shell, navigate to this directory, create a virtual environment, and install the dependencies:
```bash
python -m venv venv
.\venv\Scripts\activate      # On Windows
source venv/bin/activate    # On Unix/macOS
python -m pip install -r requirements.txt
```

### Step 2: Configure Environment
The file `.env` should be configured with the following properties:
*   `GROQ_API_KEY`: Your Groq API key.
*   `GROQ_MODEL=llama-3.3-70b-versatile`
*   `SESSION_TTL_MINUTES=30`
*   `REDIS_URL`: Supply your local Redis connection string (e.g. `redis://localhost:6379/0`) for session state caching, or leave blank to fall back to `InMemorySessionStore`.
*   `AGENT_MEMORY_URL`: The Redis Agent Memory Cloud endpoint URL (for long-term memory and session events).
*   `AGENT_MEMORY_STORE_ID`: The unique store ID for the Agent Memory Cloud.
*   `AGENT_MEMORY_API_KEY`: The authorization API key for the Agent Memory Cloud.

### Step 3: Run the Server
Start the Uvicorn server using the Python module runner to prevent absolute path launcher issues:
```bash
.\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

---

## 2. API Endpoints & Testing the Loop

### Endpoint 1: Health Check
*   **URL:** `GET http://127.0.0.1:8080/`
*   **Response:**
    ```json
    {
      "status": "UP",
      "active_workflow_specs": ["demo"],
      "model": "llama-3.3-70b-specdec",
      "session_ttl_minutes": 30
    }
    ```

---

### Endpoint 2: Chat Execution Loop (`/chat`)
This endpoint accepts citizen requests and executes the tool loop.

#### Turn 1: Get Demo Status (Non-mutating tool)
The tool `getDemoStatus` requires input `userName`. The agent will detect if it's missing, collect it, and call the tool automatically.

*   **Request:**
    ```bash
    curl -X POST http://127.0.0.1:8080/chat \
      -H "Content-Type: application/json" \
      -d '{
        "message": "Check system status. My name is CitizenA.",
        "session_id": "session-unique-1"
      }'
    ```
*   **Turn 1 Expected Response:**
    The LLM triggers the `getDemoStatus` tool under the hood, registers the parameters, and returns a natural language response:
    ```json
    {
      "response": "Hello CitizenA! The Upyog AI Agent POC status is ACTIVE. Currently, the Community Hall Booking (CHB) mock module is active, and the Advertisement module is planned.",
      "session_id": "session-unique-1",
      "collected_fields": {
        "tenantId": "pb.amritsar",
        "userName": "CitizenA"
      },
      "status": "active"
    }
    ```

#### Turn 2: Trigger Mutating Action (Gated)
The tool `triggerFakeBooking` is marked as `mutating: true` and requires `demoId`. Since it is mutating, the Orchestrator pauses, generates a confirmation prompt, and returns `status: "awaiting_confirmation"`.

*   **Request:**
    ```bash
    curl -X POST http://127.0.0.1:8080/chat \
      -H "Content-Type: application/json" \
      -d '{
        "message": "I want to reserve demo ID DEV-77",
        "session_id": "session-unique-1"
      }'
    ```
*   **Turn 2 Expected Response:**
    ```json
    {
      "response": "Confirm: Do you want to proceed with executing 'triggerFakeBooking'? (yes/no)",
      "session_id": "session-unique-1",
      "collected_fields": {
        "tenantId": "pb.amritsar",
        "userName": "CitizenA",
        "demoId": "DEV-77"
      },
      "status": "awaiting_confirmation"
    }
    ```

#### Turn 3: Confirm Mutating Action (Yes)
*   **Request:**
    ```bash
    curl -X POST http://127.0.0.1:8080/chat \
      -H "Content-Type: application/json" \
      -d '{
        "message": "yes",
        "session_id": "session-unique-1"
      }'
    ```
*   **Turn 3 Expected Response:**
    The Orchestrator processes the "yes", marks the action as confirmed, executes the mock booking, and returns the final booking number:
    ```json
    {
      "response": "Your test booking has been successfully confirmed with Booking ID DEMO-BOOK-1718814523. No actual resources have been reserved.",
      "session_id": "session-unique-1",
      "collected_fields": {
        "tenantId": "pb.amritsar",
        "userName": "CitizenA",
        "demoId": "DEV-77"
      },
      "status": "active"
    }
    ```

---

## 3. Extending into Phase 1 CHB (Read-Only Tools)

To extend this generic engine into the real **Community Hall Booking (CHB)** system, you only need to:
1.  **Add `chb.yaml` to `app/specs/`**:
    Define the read-only endpoints (e.g. `/chb-services/booking/v1/_slot-search`, `/egov-mdms-service/v1/_search`, etc.).
2.  **Add HTTP requests to `ToolExecutor`**:
    Replace mock routing with real `httpx` HTTP requests pointing to `{API_BASE}` services. Pass the citizen's authentication `token` (automatically extracted from the request Header) in the Authorization headers.
