# Refactoring Plan — Deep Scraper Agent

> Created: February 18, 2026  
> Goal: Improve readability, separation of concerns, and alignment with SOLID principles.

---

## Current State Summary

| Layer | Files | Key Problems |
|---|---|---|
| **Core** | `state.py`, `mcp_adapter.py`, `mcp_client.py`, `selector_registry.py`, `schemas.py` | Schemas split across two files; mcp_adapter and mcp_client are tightly coupled |
| **Graph Engine** | `mcp_engine.py` | Fine — small and clean |
| **Nodes** | `config.py`, `navigation.py`, `interaction.py`, `extraction.py`, `script_gen.py`, `script_test.py` | `interaction.py` is 812 lines with 3 embedded `FakePostAnalysis` classes; `config.py` is a god-module |
| **Utils** | `helpers.py`, `constants.py`, `prompts.py`, `dom.py`, `script_template.py` | `helpers.py` mixes text utils, Pydantic models, HTML cleaning, and logging; `prompts.py` is dead code |
| **Backend** | `main.py` | Script-execution logic (CSV parsing, subprocess, regex) baked directly into the route handler |
| **Frontend** | `App.tsx` | 383-line monolith — UI, API calls, state management, and data table rendering all in one |

---

## Problem Catalog (prioritized)

### 🔴 Critical — Violates SRP & makes code hard to follow

**1. `interaction.py` is an 812-line procedure with embedded fake classes**

Three anonymous `FakePostAnalysis` / `FakePostAnalysis2` / `FakePostAnalysis3` classes are created with `class FakePostAnalysis:` *inside* if-blocks inside an async function. This is a code smell that signals the function is doing too much and needs its own polymorphic flow, not duck-typed workarounds.

The full disclaimer-handling flow (visibility check → navigation click → JS fallback → accept real button → re-detect search form) should be split into smaller, named, testable functions.

**2. `config.py` is a god-module — LLM clients, browser singleton, constants re-export, and model imports all mixed together**

Every node imports `from deep_scraper.graph.nodes.config import ...` pulling everything from one place. This creates invisible coupling: changing the LLM initialization crashes all nodes.

**3. `helpers.py` has 4 unrelated responsibilities in one file**

It contains: Pydantic response models, LLM text extraction, HTML cleaning, and structured logging. These belong in separate files.

**4. `prompts.py` is dead code — the real prompts live inline in each node**

`EXPLORER_SYSTEM_PROMPT` and `CODE_GENERATION_PROMPT` in `prompts.py` are never imported anywhere. Meanwhile `navigation.py` and `interaction.py` contain hundreds of lines of hardcoded prompt strings inline.

**5. `backend/main.py` — `execute_script` route does CSV parsing, regex, subprocess, and path resolution all inline**

The 70-line route handler is a mini ETL pipeline. It is untestable and violates SRP.

---

### 🟡 Important — Readability & Maintainability

**6. Duplicate Landmark Web selector detection in 3 different places**

`landmark_patterns` dict is literally copy-pasted between `node_click_link_mcp` (twice) and `node_perform_search_mcp`. Any selector change must be made in 3 places.

**7. `AgentState` has an undeclared field `is_react_spa`**

The field is declared in `state.py` but never populated anywhere in the graph. Dead state fields make the schema misleading.

**8. Two `NavigationDecision` models exist simultaneously**

One is in `deep_scraper/core/schemas.py` (different fields) and one in `deep_scraper/utils/helpers.py` (different fields). The one from `helpers.py` is the one actually imported and used. The `schemas.py` version is silently ignored.

**9. Date-filling logic is repeated 4 times across `interaction.py`**

The pattern "try datepicker → try infragistics keyboard → try standard fill → JS fallback" is repeated for start_date and end_date independently, duplicating ~80 lines.

**10. Module boundary confusion — `schemas.py` vs `helpers.py` for Pydantic models**

`schemas.py` exists in `core/` specifically for data models, but all the node-used models (`NavigationDecision`, `PopupAnalysis`, etc.) live in `utils/helpers.py`. New developers won't know where to look.

---

### 🟢 Polish — SOLID & Clean Code

**11. `mcp_adapter.py` and `mcp_client.py` global singletons use module-level mutable state**

`get_mcp_client()` / `get_mcp_adapter()` store singletons in module-level variables. This is hard to test and makes reuse or concurrency unsafe.

**12. Backend CORS hardcodes one origin, breaking dev servers on any other port**

Vite may bind to 5173, 5174, etc. The CORS config must allow any localhost port during development.

---

## Proposed New Structure

```
deep_scraper/
├── core/
│   ├── state.py              # AgentState (unchanged — already clean)
│   ├── schemas.py            # ALL Pydantic models (consolidate from helpers.py)
│   ├── llm.py                # NEW: LLM client factory (extracted from config.py)
│   ├── browser.py            # RENAME: mcp_adapter.py → browser.py (clearer name)
│   └── mcp_client.py         # Unchanged — low-level MCP transport
│
├── graph/
│   ├── mcp_engine.py         # Unchanged — already clean
│   └── nodes/
│       ├── config.py         # SLIMMED: only re-exports; no initialization logic
│       ├── navigation.py     # Unchanged structure, prompts externalized
│       ├── disclaimer.py     # NEW: split from interaction.py
│       ├── search.py         # NEW: split from interaction.py
│       ├── extraction.py     # filter_hidden_columns moved to utils/html.py
│       ├── script_gen.py     # Unchanged — already clean
│       └── script_test.py    # Unchanged — already clean
│
└── utils/
    ├── constants.py          # Unchanged — already clean
    ├── html.py               # RENAME dom.py → html.py; absorb HTML cleaning from helpers.py
    ├── logging.py            # NEW: extract StructuredLogger from helpers.py
    ├── text.py               # NEW: extract extract_llm_text, extract_code_from_markdown
    ├── prompts.py            # REPURPOSE: move all inline prompt strings here
    └── script_template.py   # Unchanged — already clean

backend/
├── main.py                   # API routes only (thin controllers)
├── services/
│   └── script_runner.py      # NEW: subprocess execution + CSV parsing logic
└── requirements.txt          # Fix literal \n → real newlines

frontend/src/
├── App.tsx                   # Only layout + state wiring
├── api/
│   └── client.ts             # NEW: all fetch/WebSocket calls
└── components/
    ├── SearchForm.tsx         # NEW: URL/query/date inputs + Start button
    ├── ScriptLibrary.tsx      # NEW: script list + Run button
    ├── LogViewer.tsx          # NEW: real-time logs panel
    └── DataTable.tsx          # NEW: extracted results table + download
```

---

## Refactoring Steps (execution order)

### Phase 1 — Consolidate models & remove duplication (low risk)

1. **Merge `schemas.py` and the Pydantic models from `helpers.py`** into `core/schemas.py`. Update all imports.
2. **Extract `StructuredLogger`** from `helpers.py` into `utils/logging.py`.
3. **Extract text utilities** (`extract_llm_text`, `extract_code_from_markdown`, `get_site_name_from_url`) into `utils/text.py`.
4. **Merge `dom.py` HTML cleaning** with `clean_html_for_llm` from `helpers.py` into `utils/html.py`. `filter_hidden_columns_from_html` from `extraction.py` also moves here.
5. **Delete `helpers.py`** once all consumers point to new modules.
6. **Delete the dead `prompts.py`** (or repurpose it — see Phase 3).

### Phase 2 — Slim `config.py` and create `core/llm.py` (medium risk)

7. **Create `core/llm.py`** with a `LLMProvider` class or factory function that reads env vars, validates the API key, and returns the two LLM clients. This removes the module-level `raise ValueError` at import time.
8. **Create `core/browser.py`** (rename of `mcp_adapter.py`) keeping the same interface.
9. **Slim `config.py`** to only re-export what nodes need — no initialization code of its own.

### Phase 3 — Split `interaction.py` (highest payoff)

10. **Extract `_detect_landmark_selectors(html)`** as a standalone function in `utils/html.py` — eliminates the 3-way duplication.
11. **Extract `_fill_date_field(browser, selector, value, is_infragistics, is_datepicker)`** as a utility function shared between interaction nodes.
12. **Split `node_click_link_mcp`** into:
    - `_handle_normal_click(browser, selector)` — tries the LLM-provided selector
    - `_handle_alternative_navigation(browser, html, clicked_selectors)` — tries portal links
    - The main node becomes a thin orchestrator calling these.
13. **Remove `FakePostAnalysis` classes** and replace with a simple `PageState` dataclass or named tuple.
14. **Split `interaction.py`** into `nodes/disclaimer.py` and `nodes/search.py`.

### Phase 4 — Backend service layer

15. **Create `backend/services/script_runner.py`** with `run_script(path, query, start, end) -> ScriptResult` and `resolve_csv(stdout, output_dir) -> list[dict]`.
16. **Refactor `execute_script` route** to call `script_runner.run_script(...)` — reduces the route from ~70 to ~10 lines.
17. **Fix `backend/requirements.txt`** (literal `\n` → real newlines).
18. **Apply CORS regex** to allow any localhost port (dev safety).

### Phase 5 — Frontend component split

19. **Extract `api/client.ts`** with typed `fetchScripts()`, `startRun()`, and `executeScript()` functions — removes all `fetch()` calls from `App.tsx`.
20. **Extract `<ScriptLibrary />`** component (select + run button).
21. **Extract `<LogViewer />`** component (the log panel).
22. **Extract `<DataTable />`** component (results table + download).
23. **`App.tsx`** is reduced to layout and shared state wiring.

---

## Quick wins (zero risk, do these first)

| File | Fix |
|---|---|
| `backend/requirements.txt` | Replace literal `\n` with real newlines |
| `deep_scraper/core/state.py` | Remove `is_react_spa` field (never populated anywhere) |
| `deep_scraper/utils/prompts.py` | Delete the file or mark deprecated |
| `backend/main.py` | Remove `# Force reload at 21:50` comment on line 1 |
| `deep_scraper/graph/nodes/config.py` | Both `llm` and `llm_high_thinking` use identical params — they are the same object; collapse into one |

---

## SOLID Principles Mapping

| Principle | Current Violation | Fix |
|---|---|---|
| **S** — Single Responsibility | `helpers.py` owns 4 concerns; `interaction.py` is a 812-line procedure | Phases 1 + 3 |
| **O** — Open/Closed | `FakePostAnalysis` classes added inline each time new page state added | Replace with proper `PageState` dataclass |
| **L** — Liskov Substitution | Not directly violated | — |
| **I** — Interface Segregation | `config.py` forces all nodes to import the entire LLM + browser + constants bundle | Phase 2 slims config to re-exports only |
| **D** — Dependency Inversion | Nodes call `get_mcp_browser()` (module-level singleton) directly | Phase 2: inject browser via `core/llm.py` factory |
