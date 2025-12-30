# Deep Scraper Agent - Project Specification & Workflow

> **IMPORTANT**: This document defines the core workflow. Reference this before making changes.

## Project Purpose

Generate Playwright scripts that can navigate to county clerk search pages, fill search forms, 
and extract data from results grids. The agent records navigation steps and identifies grid columns.

---

## Architecture Decision: Playwright MCP

We use the **ExecuteAutomation Playwright MCP Server** for all browser operations:
- **Transport**: SSE (Server-Sent Events) on `http://localhost:8931/sse`
- **Consistency**: ALL steps use MCP - never mix MCP with direct Playwright API
- **Codegen**: Native recording via `start_codegen_session` / `end_codegen_session`

---

## Core Workflow (Step-by-Step)

```
┌──────────────────────────────────────────────────────────────┐
│  1. OPEN BROWSER (MCP)                                       │
│     - Start codegen session for recording                    │
│     - Navigate to target URL via playwright_navigate         │
├──────────────────────────────────────────────────────────────┤
│  2. GET PAGE CONTENT                                         │
│     - Use playwright_get_visible_html to get DOM             │
│     - This returns HTML that's parseable by the LLM          │
├──────────────────────────────────────────────────────────────┤
│  3. LLM ANALYZES PAGE                                        │
│     - Feed HTML to LLM                                       │
│     - LLM decides: Is this a GRID? A DISCLAIMER? A FORM?     │
│     - LLM identifies next action (click, fill, navigate)     │
├──────────────────────────────────────────────────────────────┤
│  4. EXECUTE ACTION (MCP)                                     │
│     - playwright_click, playwright_fill, etc.                │
│     - Codegen records the action automatically               │
├──────────────────────────────────────────────────────────────┤
│  5. LOOP (Repeat 2-4)                                        │
│     - Continue until LLM finds the RESULTS GRID              │
│     - Grid detection criteria: table with data rows          │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  6. GRID FOUND - CAPTURE COLUMNS                             │
│     - Get full DOM/HTML of grid                              │
│     - LLM identifies column names from known field list      │
│     - Save column mapping for script generation              │
├──────────────────────────────────────────────────────────────┤
│  7. GENERATE SCRIPT                                          │
│     - End codegen session → get recorded steps               │
│     - Save as Playwright .spec.ts file                       │
│     - Include grid column selectors in script                │
└──────────────────────────────────────────────────────────────┘
```

---

## Grid Column Field Names (Known Variations)

The LLM should recognize these field names when identifying grid columns:

### Party/Name Fields
- Party Type, Full Name, Party Name
- Cross Party Name, Search Name
- Direct Name, Reverse Name
- Grantor, Grantee, Names

### Date Fields
- Record Date, Rec Date, File Date
- Record Date Search

### Document Fields
- Type, Doc Type, Document Type
- Clerk File Number, File Number
- Instrument #, Doc Number
- Description, Legal, Legal Description

### Book/Page Fields
- Book/Page, Type Vol Page
- Rec Book, Film Code

---

## What We Are NOT Doing

1. **NO extraction during navigation** - Extraction happens when the generated script is run
2. **NO mixing MCP with direct Playwright API** - Consistency required for session management
3. **NO LLM-generated scripts** - Use native MCP codegen only

---

## Key Files

| File | Purpose |
|------|---------|
| `deep_scraper/core/mcp_client.py` | Low-level MCP SSE client |
| `deep_scraper/core/mcp_adapter.py` | High-level browser adapter |
| `deep_scraper/graph/mcp_nodes.py` | Agent node implementations |
| `deep_scraper/graph/mcp_engine.py` | Graph engine orchestration |
| `output/generated_scripts/` | Where generated scripts are saved |

---

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `playwright_navigate` | Navigate to URL |
| `playwright_click` | Click an element |
| `playwright_fill` | Fill input field |
| `playwright_get_visible_html` | Get page HTML for LLM analysis |
| `start_codegen_session` | Begin recording actions |
| `end_codegen_session` | Stop recording, generate script |

---

## Known Limitation

The `playwright_get_visible_html` tool returns **cached HTML from initial page load**.
It does NOT update after AJAX/JavaScript modifies the DOM.

**Workaround**: The generated script should include wait statements for grid loading.
When the script is run independently, it will get fresh content via `page.content()`.
