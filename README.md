# 🕵️ Deep Scraper Agent

Autonomous web navigation, search, and data extraction powered by **LangGraph + Gemini**.

## Overview

Deep Scraper Agent is an AI-powered web scraping tool that can autonomously navigate websites, handle disclaimers, fill search forms, and extract structured data from results pages. It uses Google's Gemini AI models for decision-making and Playwright for browser automation via MCP (Model Context Protocol).

## Features

- 🤖 **Autonomous Navigation**: AI-driven page analysis and decision making
- 🔍 **Smart Search**: Automatically identifies and fills search forms
- 📊 **Data Extraction**: Extracts tabular data and generates Playwright scripts
- 🎯 **Disclaimer Handling**: Automatically clicks accept/agree buttons
- 🔄 **Self-Correcting**: LLM-powered script fixing loop
- 🌐 **Modern UI**: React frontend with real-time WebSocket logs
- ⚡ **FastAPI Backend**: High-performance async API

---

## 🚀 Quick Start (Run the App)

You need **3 terminals** to run the full application:

### Terminal 1: MCP Server (Playwright)
```bash
cd "e:\Ivan (IMPORTANTE)\Ivan\Disco D\Ideas\Script Builder"
npx @executeautomation/playwright-mcp-server --port 8931
```

### Terminal 2: Backend API (FastAPI)
```bash
cd "e:\Ivan (IMPORTANTE)\Ivan\Disco D\Ideas\Script Builder\backend"
python main.py
```

### Terminal 3: Frontend (React + Vite)
```bash
cd "e:\Ivan (IMPORTANTE)\Ivan\Disco D\Ideas\Script Builder\frontend"
npm run dev
```

### Access the App
Open your browser and go to: **http://localhost:5173/**

---

## 📋 Services Summary

| Service | Port | URL | Command |
|---------|------|-----|---------|
| Frontend | 5173 | http://localhost:5173/ | `npm run dev` |
| Backend API | 8000 | http://localhost:8000/ | `python main.py` |
| MCP Server | 8931 | http://localhost:8931/ | `npx @executeautomation/playwright-mcp-server --port 8931` |

---

## Project Structure

```
deep-scraper-agent/
├── frontend/                 # React + Vite frontend
│   ├── src/                  # React components
│   ├── package.json          # Node dependencies
│   └── vite.config.ts        # Vite configuration
│
├── backend/                  # FastAPI backend
│   ├── main.py               # API entry point
│   ├── requirements.txt      # Python dependencies
│   └── output/               # Generated scripts output
│
├── deep_scraper/             # Core scraping engine
│   ├── core/                 # State, browser, schemas
│   ├── graph/                # LangGraph workflow & nodes
│   ├── utils/                # DOM helpers, prompts
│   └── compiler/             # Script generation
│
├── .env                      # Environment variables
├── requirements.txt          # Root Python dependencies
└── output/                   # Output files & data
```

---

## Installation (First-Time Setup)

1. Clone the repository:
```bash
git clone https://github.com/ivanquiroscenteno1234/deep-scraper-agent.git
cd deep-scraper-agent
```

2. Create a Python virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

3. Install Python dependencies (root + backend):
```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install chromium
```

5. Install Node.js dependencies (frontend):
```bash
cd frontend
npm install
cd ..
```

6. Set up your environment variables:
```bash
# Create .env file with your Google API key
echo GOOGLE_API_KEY=your_api_key_here > .env
```

---

## Prerequisites

Make sure you have installed:

- **Python 3.10+**: [Download Python](https://www.python.org/downloads/)
- **Node.js 18+**: [Download Node.js](https://nodejs.org/)
- **npm** (comes with Node.js)
- **Google API Key**: For Gemini AI models

---

## How It Works

1. **Navigate**: Agent navigates to the target URL via MCP-controlled browser
2. **Analyze**: LLM analyzes page content to determine page type
3. **Click/Accept**: If on a disclaimer page, clicks the accept button
4. **Search**: Fills the search form with the query and submits
5. **Capture**: Records column mappings and grid selectors
6. **Generate**: LLM generates a complete Playwright Python script
7. **Test & Fix**: Executes script and uses LLM to fix any errors

---

## Configuration

Environment variables (`.env`):
- `GOOGLE_API_KEY`: Your Google AI API key (required)
- `GEMINI_MODEL`: Model to use (default: `gemini-3-flash-preview`)

---

## Troubleshooting

### Port already in use
If a port is already in use, kill the process or use a different port:
```bash
# Check what's using a port (Windows)
netstat -ano | findstr :8931

# Kill by PID
taskkill /PID <pid> /F
```

### MCP Server not connecting
Ensure the MCP server is running before starting the backend:
```bash
npx @executeautomation/playwright-mcp-server --port 8931
```

### Frontend not loading
Make sure dependencies are installed:
```bash
cd frontend
npm install
npm run dev
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/run-agent` | POST | Start the scraper agent |
| `/api/execute-script` | POST | Execute a generated script |
| `/ws` | WebSocket | Real-time log streaming |
| `/health` | GET | Health check |

---

## 🔮 Future Implementations

Ideas and integrations to explore in future versions:

- **[Antigravity Kit](https://github.com/vudovn/antigravity-kit)** - A AI kit that could enhance the AI Experience with modern agents and skills.

---