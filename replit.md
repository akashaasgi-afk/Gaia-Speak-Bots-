# GaiaSpeak Protocol — Command Center

## Project Overview
A web-based AI chat interface for the GaiaSpeak Protocol DeFi ecosystem. Features two AI personas (Cerberus and Lilith) powered by the Groq API (SLM: llama-3.1-8b-instant / phi-4-mini class), with Qdrant Cloud for long-term memory and a cyberpunk UI in Bulgarian.

## Tech Stack
- **Backend**: Python 3.12 + Flask 3.0.0
- **Server**: Gunicorn 21.2.0 (production)
- **LLM**: Groq Cloud API — `llama-3.1-8b-instant` (fast SLM, phi-4-mini class performance)
- **Long-term Memory**: Qdrant Cloud vector database (`gaiaspeak_memory` collection)
- **Frontend**: Vanilla HTML/CSS/JS embedded in Flask template string

## Project Structure
```
main.py          # Complete Flask app with embedded HTML/CSS/JS frontend
requirements.txt # Python dependencies (flask, gunicorn, qdrant-client)
memory.json      # (legacy) local memory fallback
```

## Running the App
- **Production**: `gunicorn --bind=0.0.0.0:5000 --reuse-port --workers=1 main:app`

## Environment Variables / Secrets Required
- `QDRANT_URL` — Qdrant Cloud cluster URL
- `QDRANT_API_KEY` — Qdrant Cloud API key
- `GROQ_API_KEY` — Entered by user in browser UI (stored in localStorage, never sent to server)

## API Endpoints
- `GET /` — Main UI
- `GET /api/status` — System status (model, Qdrant connectivity)
- `POST /api/memory/save` — Save event to Qdrant (`{agent, role, content, event_type}`)
- `GET /api/memory/recent?agent=cerberus&limit=10` — Retrieve recent memory events

## Key Features
- Dual AI personas: Cerberus (guardian) and Lilith (strategist)
- SLM model: `llama-3.1-8b-instant` — fast, efficient inference via Groq
- Qdrant Cloud long-term memory: stores all trading logs and security events
- Client-side Groq API calls (API key stored in browser localStorage only)
- Voice input (Web Speech API) and text-to-speech output
- File upload support (txt, pdf, doc)
- "Both" mode for simultaneous responses from both agents
- All communication in Bulgarian
- Header badge shows QDRANT: CONNECTED / OFFLINE status

## Architecture Notes
- The entire frontend is a single embedded template string in `main.py`
- No build system — pure Python/HTML/CSS/JS
- Groq API key never sent to the server — stays in the browser
- Chat history stored in localStorage (short-term) + Qdrant (long-term)
- Qdrant collection `gaiaspeak_memory` has keyword index on `agent` field for fast filtered queries
