from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field

class NavigationDecision(BaseModel):
    """Decides if the current page is the target search page or needs navigation."""
    is_search_page: bool = Field(description="True ONLY if there is a visible TEXT INPUT field for entering a name/search term AND a search/submit button. Navigation links alone don't count.")
    is_disclaimer_page: bool = Field(
        default=False,
        description="True if this is a terms/conditions/disclaimer page with an 'Accept' or 'I Agree' button that must be clicked first."
    )
    requires_login: bool = Field(
        default=False,
        description="True if the page requires login credentials (has username/password fields or 'Sign In' button)."
    )
    reasoning: str = Field(description="Reasoning for this decision based on page content.")
    suggested_link_selector: Optional[str] = Field(
        default=None, 
        description="CSS selector to click: either the Accept/Agree button (if disclaimer) or navigation link to search page."
    )
    confidence_score: float = Field(description="Confidence score between 0.0 and 1.0")

class SearchFormDetails(BaseModel):
    """Details identifying the search form elements."""
    input_selector: str = Field(description="The CSS selector for the 'Name/Party' input field")
    submit_button_selector: str = Field(description="The CSS selector for the 'Search' button")
    requires_date_range: bool = Field(
        default=False, 
        description="Does the form require filling dates? Default False"
    )

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
