---
name: site-pattern-detector
description: Identifies county clerk site types (AcclaimWeb, Landmark Web, ASP.NET ListView) from URL patterns and HTML structure to apply correct handling strategies.
---
# Site Pattern Detector

## When to Use
Before debugging navigation issues, identify the site type first. Each type has unique patterns for disclaimers, popups, and grids.

## Site Type Detection

### 1. AcclaimWeb (Telerik Grids)
**URL Patterns:**
```
*brevardclerk.us/AcclaimWeb/*
*vaclmweb*.*/AcclaimWeb/*
```

**HTML Signatures:**
- Grid: `#RsltsGrid`, `.t-grid`, `.t-grid-content`
- Popup: `#NamesWin`, `#frmSchTarget` with `input[value='Done']`
- Search inputs: `#SearchOnName`, `#RecordDateFrom`, `#RecordDateTo`

**Handling:**
- Popup appears after search with name selection
- Click "Done" button to proceed to results
- Grid uses Telerik controls

---

### 2. Landmark Web (Modal-Based)
**URL Patterns:**
```
*flaglerclerk.com*
*records.*.gov*
```

**HTML Signatures:**
- Home page: Icons for "Name Search", "Document Search", etc.
- Modal: `#disclaimer` with `class="modal hide"` (hidden until clicked)
- Accept button: `#idAcceptYes`
- Search inputs appear IN modal: `#name-Name`, `#beginDate-Name`

**Handling:**
- **CRITICAL**: Must click search type icon FIRST (e.g., `a[title='Name Search']`)
- This reveals the disclaimer modal
- Click Accept, then search form appears in same modal
- Grid: `#resultsTable` with DataTables

---

### 3. ASP.NET ListView
**URL Patterns:**
```
*cclerk.hctx.net*
*publicsearch.us*
```

**HTML Signatures:**
- Grid: `#itemPlaceholderContainer`, `[id*='ListView']`
- Uses `<table>` with Bootstrap classes: `.table-condensed`, `.table-striped`
- No DataTables, just plain HTML tables

**Handling:**
- Often has disclaimer on same page (not modal)
- Grid rows are direct `<tr>` elements
- May use `<span>` for cell content instead of direct text

---

## Quick Reference Table

| Site Type | Disclaimer | Popup After Search | Grid Selector |
|-----------|------------|-------------------|---------------|
| AcclaimWeb | Same page | Yes - NamesWin | `#RsltsGrid`, `.t-grid` |
| Landmark Web | Modal (click icon first) | No | `#resultsTable` |
| ASP.NET ListView | Same page | Varies | `#itemPlaceholderContainer` |

## Detection Script
```python
def detect_site_type(url: str, html: str) -> str:
    if "AcclaimWeb" in url:
        return "ACCLAIMWEB"
    if "flaglerclerk" in url or "#disclaimer" in html:
        return "LANDMARK_WEB"
    if "itemPlaceholderContainer" in html or "ListView" in html:
        return "ASPNET_LISTVIEW"
    return "UNKNOWN"
```
