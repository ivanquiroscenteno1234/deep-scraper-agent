"""
Schemas — All Pydantic models for the Deep Scraper Agent.

Consolidated from:
- deep_scraper/core/schemas.py (original)
- deep_scraper/utils/helpers.py (NavigationDecision, PopupAnalysis, etc.)
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Navigation & page-classification models
# ---------------------------------------------------------------------------

class NavigationDecision(BaseModel):
    """Decision about what the current page represents."""
    is_search_page: bool = Field(description="True if this is a search form page")
    is_results_grid: bool = Field(description="True if this page has a data grid/table with search results")
    is_disclaimer: bool = Field(description="True if this is a disclaimer/acceptance page")
    requires_login: bool = Field(description="True if login is required")
    reasoning: str = Field(description="Brief explanation of the decision")
    accept_button_ref: str = Field(default="", description="CSS selector for accept button if disclaimer")
    search_input_ref: str = Field(default="", description="CSS selector for search input if search page")
    search_button_ref: str = Field(default="", description="CSS selector for search button if search page")
    start_date_input_ref: str = Field(default="", description="CSS selector for start date input if search page (e.g. #RecordDateFrom)")
    end_date_input_ref: str = Field(default="", description="CSS selector for end date input if search page (e.g. #RecordDateTo)")
    grid_selector: str = Field(default="", description="CSS selector for data grid/table if results grid")


class SearchFormDetails(BaseModel):
    """Details identifying the search form elements."""
    input_selector: str = Field(description="The CSS selector for the 'Name/Party' input field")
    submit_button_selector: str = Field(description="The CSS selector for the 'Search' button")
    requires_date_range: bool = Field(
        default=False,
        description="Does the form require filling dates? Default False"
    )


# ---------------------------------------------------------------------------
# Post-interaction analysis models
# ---------------------------------------------------------------------------

class PopupAnalysis(BaseModel):
    """Analysis result for popup detection after search."""
    has_popup: bool = Field(description="True if there's a popup/modal requiring user action before results")
    popup_selector: str = Field(default="", description="CSS selector for the popup container if present")
    action_button_selector: str = Field(default="", description="CSS selector for the button to click (e.g., Done, Submit, OK)")
    description: str = Field(description="Brief description of what was found")


class PostClickAnalysis(BaseModel):
    """Analysis result after clicking a button."""
    page_changed: bool = Field(description="True if the page content changed after the click")
    is_search_page: bool = Field(description="True if we're now on a search form page")
    still_on_disclaimer: bool = Field(description="True if still showing disclaimer/accept content")
    description: str = Field(description="Brief description of current page state")


class PostPopupAnalysis(BaseModel):
    """Analysis result after handling a popup."""
    has_results_grid: bool = Field(description="True if results grid/table is now visible")
    grid_selector: str = Field(default="", description="CSS selector for the results grid if found")
    needs_more_action: bool = Field(description="True if another action is needed before results appear")
    next_action: str = Field(default="", description="Description of next action needed, if any")


# ---------------------------------------------------------------------------
# Data extraction models
# ---------------------------------------------------------------------------

class ColumnAnalysis(BaseModel):
    """Analysis result for grid column detection."""
    grid_selector: str = Field(description="Primary CSS selector for the grid")
    row_selector: str = Field(description="CSS selector for data rows")
    columns: list = Field(description="List of column names found")


class ExtractionResult(BaseModel):
    """Results of the extraction analysis."""
    has_data: bool = Field(description="Did the search return visible results? Look for tables, grids, or lists with record data.")
    data_structure_type: str = Field(description="Type of data structure: 'TABLE', 'GRID', 'LIST', or 'NONE'")
    row_selector: str = Field(description="The CSS selector for the individual data rows (e.g., 'table tbody tr', '.result-row', '#results tr')")
    container_selector: Optional[str] = Field(default=None, description="The CSS selector for the results container if applicable")
    column_names: List[str] = Field(default=[], description="List of column/field names visible in the results (e.g., ['Name', 'Date', 'Document Type', 'Book/Page'])")
    no_results_message: Optional[str] = Field(default=None, description="If no data, what message indicates no results were found?")


class ParsedRecord(BaseModel):
    """A single parsed record from the search results."""
    fields: Dict[str, str] = Field(description="Dictionary of field names to values extracted from the record")
