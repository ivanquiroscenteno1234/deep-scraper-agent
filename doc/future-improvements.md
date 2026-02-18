# Future Improvements Roadmap

This document captures the next high-impact improvements for Deep Scraper Agent.

## 1) Standardize output folders for generated scripts and data

### Goal
Unify where generated scripts and extracted data are stored, regardless of whether output comes from backend execution, tests, or manual script runs.

### Current issue
- Output currently appears in multiple similar paths (for example under `backend/output` and root `output`).
- This creates confusion when locating artifacts and increases maintenance overhead.

### Proposed approach
- Define a single canonical output root (recommended: `output/`).
- Use fixed subfolders:
  - `output/generated_scripts/`
  - `output/data/`
  - `output/logs/` (optional, for future traceability)
- Centralize path resolution in one utility/module (for example in `deep_scraper/utils/constants.py` or a new output-path service).
- Replace hardcoded output paths across backend services and graph nodes with this centralized helper.

### Acceptance criteria
- All script and data artifacts are written only under the canonical output root.
- No module writes to `backend/output` unless explicitly intended and documented.
- README and any workflow docs reflect the standardized structure.

---

## 2) Standardize output column names and data normalization

### Goal
Ensure all exported datasets use consistent column naming and normalized values across sites.

### Current issue
- Column names are discovered dynamically and can differ by source (case, spacing, punctuation, aliases).
- Downstream consumers must handle inconsistent schemas.

### Proposed approach
Option A (preferred): add a dedicated post-capture normalization step in the agent graph.
- New node (example): `node_standardize_output`
- Runs after extraction and before final CSV/script output.

Responsibilities:
- Map discovered columns to canonical schema names.
- Normalize formatting (trim whitespace, date format, numeric formatting, null handling).
- Track unmapped columns in metadata/log output.

Supporting artifacts:
- Add a schema mapping config (YAML/JSON/Python dict) for aliases and canonical names.
- Include site-specific override maps when needed.

### Acceptance criteria
- CSV outputs use stable canonical headers.
- Value formats are normalized consistently (dates, numbers, blanks).
- Unknown/unmapped source columns are reported without breaking export.

---

## 3) Add 1-second wait between generated script steps

### Goal
Improve runtime stability of generated Playwright scripts by introducing short waits between actions.

### Proposed approach
- Update script-generation prompt guidance to require a 1-second delay between interaction steps.
- Ensure generated Playwright code includes a delay call between sequential actions, for example:
  - `await page.wait_for_timeout(1000)` in async style
  - equivalent sync delay pattern if sync Playwright is used in generated templates
- Avoid adding waits where they are not meaningful (for example after final action before process exit).

### Validation checks
- Generated scripts consistently include delay statements between major actions (goto, click, fill, submit, navigation transitions).
- Existing success criteria (`SUCCESS` marker and positive row count) still pass.
- Keep this behavior configurable later via constant/env (future enhancement).

---

## 4) Refactor for separation of concerns, readability, and SOLID principles

### Goal
Refactor core modules to reduce coupling and improve maintainability while preserving behavior.

### Focus areas
- Separation of concerns
  - Isolate browser orchestration, LLM decision logic, and output persistence.
  - Keep graph nodes thin; move heavy logic into focused services.
- Readability
  - Reduce long functions and deeply nested conditionals.
  - Standardize naming and simplify control flow.
- SOLID principles
  - Single Responsibility: each service/module has one clear purpose.
  - Open/Closed: enable extension (new site heuristics, mappings) with minimal core changes.
  - Liskov/Interface Segregation: define clear interfaces for browser and LLM adapters.
  - Dependency Inversion: inject dependencies for easier testing/mocking.

### Suggested implementation phases
1. Baseline and boundaries
   - Document current responsibilities per module.
   - Mark high-change/high-risk files first.
2. Extract services
   - Move reusable logic from graph nodes into service classes/functions.
3. Introduce interfaces
   - Add clean contracts for LLM client, browser adapter, and output writer.
4. Stabilize tests and docs
   - Add/adjust targeted tests for refactored behavior.
   - Update docs for architecture and extension points.

### Acceptance criteria
- No functional regressions in main workflow.
- Reduced function complexity in core orchestration modules.
- Clear service boundaries and fewer hardcoded cross-module dependencies.

---

## Recommended execution order
1. Standardize output folders
2. Standardize output columns/data
3. Add 1-second waits to generated scripts
4. Perform SOLID-focused refactor (incremental)

This order minimizes migration risk and creates a stable base for broader refactoring.
