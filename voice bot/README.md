# UPYOG Voice Bot Integration Files

This directory contains modified versions of `app.py` and `index.html` adapted from the **UPYOG Voice Bot (dev 2.0)** repository. They have been updated to be fully in sync and integrated with the UPYOG AI Action-Agent backend.

---

## 1. What's Inside

*   **[app.py](file:///d:/UMEED%20chatbot/AI%20Action-Agent/ai-agent/voice%20bot/app.py)**: The Flask application serving the Voice Bot logic. It classifies user intents (e.g. FAQ, Grievance, or Booking) and automatically proxies booking-specific conversation turns to the running FastAPI AI Action-Agent service at `http://127.0.0.1:8080/chat`.
*   **[index.html](file:///d:/UMEED%20chatbot/AI%20Action-Agent/ai-agent/voice%20bot/index.html)**: The frontend user interface. It features a new **Advanced Authentication Panel** allowing you to test login states using either a raw citizen mobile number or a real UPYOG **Portal Auth Token** and **User Info JSON** payload block.

---

## 2. Integration & Testing Steps

To test the AI Action-Agent using the voice bot interface:

### Step 1: Copy Files into Voice Bot Project
Copy these files (`app.py` and `index.html`) from this directory and paste them into your local **UPYOG Voice Bot (dev 2.0)** repository, replacing the original files.

### Step 2: Ensure Action-Agent Backend is Running
Verify that the UPYOG AI Action-Agent FastAPI server is running locally on port `8080`:
```bash
# In the UPYOG-AI-Action-Agent repository:
.\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

### Step 3: Run the Voice Bot Server
Run the Flask application within the voice bot environment (which starts on port `8090` by default):
```bash
# In your voice bot project folder:
python app.py
```

### Step 4: Open and Test
1.  Open the voice bot web application in your browser (e.g. `http://localhost:8090`).
2.  Click **Advanced: Use Portal Auth Token** in the login modal.
3.  Provide the `authToken` and the `userInfo` JSON payload.
4.  Interact via text or voice. Start booking a community hall, cancel/confirm, or ask questions to verify the end-to-end integration!
