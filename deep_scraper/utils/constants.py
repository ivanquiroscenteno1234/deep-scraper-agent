"""
Constants module - All configuration constants for the Deep Scraper Agent.

Centralizes:
- Grid selectors for various county clerk sites
- Known column names
- Default timeouts
- Site-specific configurations
"""

from typing import List, Dict

# ============================================================================
# GRID SELECTORS (for waiting/detection only, NOT for recording)
# ============================================================================

RESULTS_GRID_SELECTORS: List[str] = [
    # Brevard County / AcclaimWeb sites (Telerik grids)
    "#RsltsGrid",
    ".t-grid",
    ".t-grid-content",
    # Flagler County / DataTree sites
    "#resultsTable",
    "#resultsTable_wrapper",
    # Dallas County / PublicSearch sites
    ".search-results__results-wrap",
    ".a11y-table",
    ".a11y-table table",
    # Miami-Dade County / Custom Angular sites
    ".custom-table",
    ".table-responsive table",
    "table.align-middle",
    # Travis County / Aumentum Recorder (Infragistics grids)
    ".ig_ElectricBlueControl",
    ".igg_ElectricBlueControl",
    "[id*='_g_G1']",
    # Generic fallbacks (for detection only)
    "#SearchGrid",
    "#SearchGridDiv table",
    ".searchGridDiv table",
    "#grdSearchResults",
    "#gridMain",
    "table.dataTable",
]

# ============================================================================
# KNOWN COLUMN NAMES (for LLM to recognize)
# ============================================================================

KNOWN_GRID_COLUMNS: List[str] = [
    # Party/Name Fields
    "Party Type", "Full Name", "Party Name", "Cross Party Name", "Search Name",
    "Direct Name", "Reverse Name", "Grantor", "Grantee", "Names",
    # Date Fields
    "Record Date", "Rec Date", "File Date", "Record Date Search",
    # Document Fields
    "Type", "Doc Type", "Document Type", "Clerk File Number", "File Number",
    "Instrument #", "Doc Number", "Description", "Legal", "Legal Description",
    # Book/Page Fields
    "Book/Page", "Type Vol Page", "Rec Book", "Film Code",
    # Other
    "Consideration", "Case #", "Comments"
]

# ============================================================================
# TIMEOUTS (in milliseconds)
# ============================================================================

DEFAULT_NAVIGATION_TIMEOUT = 30000
DEFAULT_ELEMENT_TIMEOUT = 10000
DEFAULT_GRID_WAIT_TIMEOUT = 15000

# ============================================================================
# SCRIPT GENERATION SETTINGS
# ============================================================================

MAX_SCRIPT_FIX_ATTEMPTS = 3
SCRIPT_TEST_TIMEOUT_SECONDS = 120

# ============================================================================
# LLM SETTINGS
# ============================================================================

DEFAULT_HTML_LIMIT = 50000
POPUP_HTML_LIMIT = 60000  # Extra for popup detection since popups can be at end of DOM
COLUMN_HTML_LIMIT = 50000
