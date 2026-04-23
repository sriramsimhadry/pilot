# ✈ Agentic AI Workflow for Aeroplanes

A fully local multi-agent AI system that automates flight search and booking (until payment) on MakeMyTrip — with a live, visible browser you can watch in real time.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Mission      │  │  Live Browser    │  │  Agent Logs      │  │
│  │ Control      │  │  Panel           │  │  Stream          │  │
│  │ (Chat+Flights│  │  (Screenshots)   │  │  (Real-time)     │  │
│  └──────────────┘  └──────────────────┘  └──────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket + REST
┌──────────────────────────▼──────────────────────────────────────┐
│                     FastAPI Backend                             │
│  ┌─────────────┐  ┌─────────────────────────────────────────┐  │
│  │  REST API   │  │         Workflow Orchestrator            │  │
│  │  /api/*     │  │                                         │  │
│  └─────────────┘  │  ┌──────────┐  ┌──────────────────────┐ │  │
│                   │  │ Planner  │  │   Browser Agent      │ │  │
│  ┌─────────────┐  │  │ Agent    │  │   (Playwright)       │ │  │
│  │  WebSocket  │  │  └──────────┘  └──────────────────────┘ │  │
│  │  /ws/{id}   │  │  ┌──────────┐  ┌──────────────────────┐ │  │
│  └─────────────┘  │  │ Vision   │  │  Extraction Agent    │ │  │
│                   │  │ Agent    │  └──────────────────────┘ │  │
│                   │  └──────────┘  ┌──────────────────────┐ │  │
│                   │                │  Form Filling Agent  │ │  │
│                   │                └──────────────────────┘ │  │
│                   └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   Visible Chromium      │
              │   Browser (Playwright)  │
              │   makemytrip.com        │
              └─────────────────────────┘
```

---

## Agents

| Agent | Role |
|-------|------|
| **Planner Agent** | Parses natural language query → structured JSON plan |
| **Browser Agent** | Playwright automation in visible mode with human delays |
| **Vision Agent** | Claude vision for UI detection when DOM selectors fail |
| **Extraction Agent** | Multi-strategy HTML parser for flight data |
| **Form Filling Agent** | Passenger form automation + payment page detection |
| **Orchestrator** | Coordinates all agents, manages state, handles errors |

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Git**

---

## Setup Instructions

### 1. Clone / Navigate to Project

```bash
cd agentic-aeroplane
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers (this downloads Chromium)
playwright install chromium
playwright install-deps chromium   # Linux only - installs system deps
```

### 3. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your Anthropic API key (optional but recommended for Vision Agent)
# ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Note:** The Anthropic API key is optional. Without it, the Vision Agent is disabled, but the system still works using DOM-based selectors and heuristic extraction.

### 4. Frontend Setup

```bash
cd ../frontend

# Install Node dependencies
npm install
```

---

## Running the Application

You need **two terminal windows**.

### Terminal 1 — Backend

```bash
cd backend
source venv/bin/activate   # or venv\Scripts\activate on Windows

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

You should see:
```
  VITE v5.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

### 3. Open Your Browser

Navigate to: **http://localhost:5173**

---

## Using the Application

### Step-by-Step Workflow

1. **Enter a query** in the Mission Control panel:
   - `"Hyderabad to Delhi tomorrow"`
   - `"Mumbai to Bangalore this Friday"`
   - `"Delhi to Goa next Monday 2 passengers"`

2. **Click "LAUNCH AGENT"** — this starts the workflow

3. **Watch the Live Browser panel** — switch to "Live Browser" tab to see Chromium open and operate MakeMyTrip in real time

4. **Monitor Agent Logs** — switch to "Agent Logs" tab to see every decision the agents make

5. **Select a flight** — once results are extracted, they appear in Mission Control. Click a flight to select it.

6. **Enter passenger details** — a form appears for name, age, gender, email, phone

7. **Agent fills the form** — watch the browser as the agent types in your details

8. **Auto-stop before payment** — the system detects the payment page and halts

---

## Project Structure

```
agentic-aeroplane/
├── backend/
│   ├── main.py                      # FastAPI app, routes, WebSocket
│   ├── requirements.txt
│   ├── .env.example
│   ├── agents/
│   │   ├── planner_agent.py         # NLP query parser → JSON plan
│   │   ├── browser_agent.py         # Playwright visible browser
│   │   ├── vision_agent.py          # Claude vision API
│   │   ├── extraction_agent.py      # HTML flight data parser
│   │   ├── form_filling_agent.py    # Passenger form + payment detection
│   │   └── workflow_orchestrator.py # Coordinates all agents
│   ├── api/
│   │   └── models.py                # Pydantic request/response models
│   └── utils/
│       ├── connection_manager.py    # WebSocket manager
│       └── logger.py                # Structured agent logger
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx / App.module.css
        ├── index.css                # Global styles + CSS variables
        ├── store/
        │   └── useStore.js          # Zustand state + WebSocket
        └── components/
            ├── Header.jsx           # Nav tabs + status indicator
            ├── StatusBar.jsx        # Workflow step progress
            ├── ChatPanel.jsx        # Query input + flight results
            ├── FlightCard.jsx       # Individual flight display
            ├── PlanView.jsx         # Execution plan display
            ├── BrowserPanel.jsx     # Live screenshot stream
            ├── LogsPanel.jsx        # Real-time log stream
            └── PassengerModal.jsx   # Passenger details form
```

---

## Key Technical Features

### Browser Agent
- **Visible mode** — Chromium runs in a real window you can observe
- **Human-like delays** — Random 50–150ms keystroke timing, natural pauses
- **Multi-selector fallback** — Tries 5–8 CSS selectors per action before failing
- **Popup auto-removal** — DOM manipulation + Escape key + JS injection
- **Screenshot loop** — Captures every 1.5s and streams via WebSocket
- **Automation detection bypass** — Removes `navigator.webdriver` flag

### Extraction Agent
Three-strategy pipeline:
1. **JSON-LD / Embedded JSON** — Fastest, looks for `window.__data`
2. **CSS Card Selectors** — Uses known MakeMyTrip class patterns
3. **Heuristic Text Mining** — Pattern-matches time/price/airline in raw text

### Vision Agent (requires API key)
- Uses `claude-opus-4-5` with vision capability
- Called only when DOM selectors fail (DOM-first approach)
- Returns coordinates for clicking + selector hints
- Detects popups, page states, and form fields

### Form Filling Agent
- Fills title, first/last name, age, DOB, gender, email, phone
- Detects payment page via URL patterns + 3+ payment keyword matches
- Halts the entire workflow before any payment is possible

### Error Recovery
- All browser actions wrapped in try/catch with selector fallbacks
- Vision Agent invoked automatically on DOM failures
- Workflow continues gracefully on non-critical errors
- All errors logged and broadcast to frontend

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/workflow/start` | Start a new workflow |
| `POST` | `/api/workflow/{id}/passenger` | Submit passenger details |
| `POST` | `/api/workflow/{id}/select-flight` | Select a flight |
| `POST` | `/api/workflow/{id}/stop` | Stop workflow + close browser |
| `GET` | `/api/workflow/{id}/status` | Get current status |
| `WS` | `/ws/{id}` | WebSocket for real-time updates |

### WebSocket Message Types

| Type | Direction | Description |
|------|-----------|-------------|
| `log` | Server→Client | Agent log entry |
| `screenshot` | Server→Client | Base64 JPEG screenshot |
| `stage` | Server→Client | Workflow stage change |
| `flights` | Server→Client | Extracted flight data |
| `plan` | Server→Client | Generated execution plan |
| `error` | Server→Client | Error occurred |
| `ping/pong` | Bidirectional | Keepalive |

---

## Troubleshooting

### "Browser doesn't open"
```bash
# Make sure playwright browsers are installed
playwright install chromium
# On Linux, also run:
playwright install-deps
```

### "No flights extracted"
- MakeMyTrip frequently updates their DOM structure
- The system falls back to demo flights automatically for demonstration
- Enable the Vision Agent (set `ANTHROPIC_API_KEY`) for better extraction
- Check the Agent Logs panel for detailed error messages

### "WebSocket not connecting"
- Ensure the backend is running on port 8000
- Check browser console for connection errors
- The Vite dev server proxies `/ws` to `localhost:8000`

### "Popup not dismissed"
- The agent tries 3 rounds of popup removal
- Enable Vision Agent for AI-powered popup detection
- MakeMyTrip's login modal is aggressively handled via JS DOM removal

### CORS errors
- Backend CORS is configured for `localhost:5173` and `localhost:3000`
- If using a different port, update `allow_origins` in `backend/main.py`

---

## Security & Ethics Notes

- **No payment execution** — The system is hard-coded to stop at payment detection
- **No CAPTCHA solving** — If a CAPTCHA appears, the workflow will pause
- **No credentials stored** — No MakeMyTrip account login is performed
- **Local only** — All data stays on your machine
- **Rate limiting** — Human-like delays prevent aggressive scraping

---

## Extending the System

### Adding New Airlines
Edit `CITIES` dict in `agents/planner_agent.py`

### Supporting Round-Trip
Add `round_trip` parsing in `PlannerAgent._extract_class()` and extend the steps in `_build_steps()`

### Adding More Sites
Create a new `BrowserAgent` subclass with site-specific selectors

### Improving Extraction
Add new selector patterns to `ExtractionAgent.FLIGHT_CARD_SELECTORS`

---

## License

MIT — For educational and personal use only. Do not use for commercial automation.
