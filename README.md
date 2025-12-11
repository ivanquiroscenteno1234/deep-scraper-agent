# 🕵️ Deep Scraper Agent

Autonomous web navigation, search, and data extraction powered by **LangGraph + Gemini**.

## Overview

Deep Scraper Agent is an AI-powered web scraping tool that can autonomously navigate websites, handle disclaimers, fill search forms, and extract structured data from results pages. It uses Google's Gemini AI models for decision-making and Playwright for browser automation.

## Features

- 🤖 **Autonomous Navigation**: AI-driven page analysis and decision making
- 🔍 **Smart Search**: Automatically identifies and fills search forms
- 📊 **Data Extraction**: Extracts tabular data and saves to CSV
- 🎯 **Disclaimer Handling**: Automatically clicks accept/agree buttons
- 🔄 **Self-Correcting**: Fallback strategies for robust element interaction

## Project Structure

```
deep-scraper-agent/
├── app.py                    # Streamlit UI entry point
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (GOOGLE_API_KEY)
│
├── deep_scraper/             # Main package
│   ├── core/                 # Core components
│   │   ├── state.py          # Agent state definition
│   │   ├── browser.py        # Playwright browser manager
│   │   └── schemas.py        # Pydantic models for LLM output
│   │
│   ├── graph/                # LangGraph engine
│   │   ├── engine.py         # Graph workflow definition
│   │   └── nodes.py          # Node implementations
│   │
│   ├── agents/               # Alternative agent implementations
│   │   ├── explorer.py       # Tool-calling explorer agent
│   │   └── visual.py         # Visual/screenshot-based agent
│   │
│   ├── utils/                # Utilities
│   │   ├── dom.py            # DOM simplification helpers
│   │   └── prompts.py        # LLM system prompts
│   │
│   └── compiler/             # Script generation
│       ├── compiler.py       # Converts steps to Playwright scripts
│       └── template.py       # Script templates
│
├── output/                   # Output files
│   └── extracted_data/       # Saved CSV results
│
└── tests/                    # Test suite
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ivanquiroscenteno1234/deep-scraper-agent.git
cd deep-scraper-agent
```

2. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

4. Set up your environment:
```bash
# Create .env file with your Google API key
echo GOOGLE_API_KEY=your_api_key_here > .env
```

## Usage

### Running the Streamlit App

```bash
streamlit run app.py
```

This launches a web UI where you can:
1. Enter a target URL (e.g., a county clerk search page)
2. Enter a search term (e.g., a name to search for)
3. Click "Launch Agent" to start the autonomous scraping

### Running the Graph Engine Directly

```python
import asyncio
from deep_scraper.graph.engine import app
from deep_scraper.core.state import AgentState
from deep_scraper.core.browser import BrowserManager

async def main():
    initial_state = AgentState(
        target_url="https://example.com/search",
        search_query="John Smith",
        current_page_summary="",
        logs=[],
        attempt_count=0,
        status="NAVIGATING",
        extracted_data=[],
        search_selectors={}
    )
    
    async for output in app.astream(initial_state):
        print(output)
    
    # Cleanup
    browser = BrowserManager()
    await browser.close()

asyncio.run(main())
```

## How It Works

1. **Navigate**: Agent navigates to the target URL
2. **Analyze**: LLM analyzes page content to determine if it's the search page
3. **Click/Accept**: If on a disclaimer page, clicks the accept button
4. **Search**: Fills the search form with the query and submits
5. **Extract**: Parses the results table and saves data to CSV

## Configuration

Environment variables (`.env`):
- `GOOGLE_API_KEY`: Your Google AI API key (required)
- `GEMINI_MODEL`: Model to use (default: `gemini-2.0-flash-exp`)

## License

MIT License
