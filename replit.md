# GaiaSpeak Protocol — Command Center

## Project Overview
A web-based AI chat interface for the GaiaSpeak Protocol DeFi ecosystem. Features two AI personas (Cerberus and Lilith) powered by the Groq API, with a cyberpunk/terminal-style UI in Bulgarian.

## Tech Stack
- **Backend**: Python 3.12 + Flask 3.0.0
- **Server**: Gunicorn 21.2.0 (production)
- **Frontend**: Vanilla HTML/CSS/JS embedded in Flask template string
- **AI**: Groq Cloud API (llama-3.3-70b-versatile) — called client-side

## Project Structure
```
main.py          # Complete Flask app with embedded HTML/CSS/JS frontend
requirements.txt # Python dependencies
memory.json      # Persistent memory storage (auto-created at runtime)
```

## Running the App
- **Development**: `python main.py` (port 5000, host 0.0.0.0)
- **Production**: `gunicorn --bind=0.0.0.0:5000 --reuse-port main:app`

## Key Features
- Dual AI personas: Cerberus (guardian) and Lilith (strategist)
- Client-side Groq API calls (API key stored in browser localStorage)
- Voice input (Web Speech API) and text-to-speech output
- File upload support (txt, pdf, doc)
- "Both" mode for simultaneous responses from both agents
- All communication in Bulgarian

## Architecture Notes
- The entire frontend is a single embedded template string in `main.py`
- No build system — pure Python/HTML/CSS/JS
- API key never sent to the server — stays in the browser
- Chat history stored in localStorage
