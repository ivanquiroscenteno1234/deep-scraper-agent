---
name: test-script-builder
description: End-to-end testing workflow for the Deep Scraper Agent, including test sites and success criteria.
---
# Test Script Builder Agent

## Prerequisites
1. **MCP Server**: Chrome DevTools MCP must be running
2. **Backend**: FastAPI server at `localhost:8000`
3. **No frontend required**: Testing uses API directly

## Test Sites

### Brevard County (AcclaimWeb - Telerik Grid)
```
URL: https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName
Search: Lauren Homes
Dates: 01/01/1980 - 01/06/2026
```
**Characteristics:** Telerik grid, name selection popup with Done button

### Flagler County (Landmark Web - Modal-based)
```
URL: https://records.flaglerclerk.com/
Search: ESSEX HOME MORTGAGE SERVICING CORP
Dates: 01/01/1992 - 12/31/1992
```
**Characteristics:** Modal navigation, must click Name Search icon before disclaimer

### Harris County (ASP.NET ListView)
```
URL: https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx
Search: SMITH
Dates: 01/01/2024 - 12/31/2024
```
**Characteristics:** ListView grid pattern, `#itemPlaceholderContainer`

## Success Criteria
1. ✅ Agent navigates to URL
2. ✅ Handles disclaimers/popups
3. ✅ Fills search form with term and dates
4. ✅ Discovers grid and columns
5. ✅ Generates Playwright script
6. ✅ Script test passes (or fixes within 3 attempts)
7. ✅ CSV file created in `backend/output/data/`

## Running Tests

### Via API
```bash
curl -X POST "http://localhost:8000/api/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName",
    "search_term": "Lauren Homes",
    "start_date": "01/01/1980",
    "end_date": "01/06/2026"
  }'
```

### Via WebSocket (for real-time logs)
Connect to `ws://localhost:8000/ws/agent/{session_id}` after starting run.

## Debugging Failed Tests

1. **Check logs**: Look for `[Analyze]`, `[ClickLink]`, `[Search]` patterns
2. **Review status transitions**: `NAVIGATING → SEARCH_PAGE_FOUND → SEARCH_EXECUTED → COLUMNS_CAPTURED → SCRIPT_GENERATED`
3. **Inspect generated script**: `backend/output/generated_scripts/`
4. **Check error screenshots**: `backend/error_state_*.png`

## Common Failure Patterns

| Status | Cause | Investigation |
|--------|-------|---------------|
| Stuck at NAVIGATING | Disclaimer loop | Check `disclaimer_click_attempts` |
| COLUMNS_CAPTURED but script fails | Wrong grid selector | Verify `discovered_grid_selectors` |
| Script times out | Missing wait or popup | Review script popup handling |
