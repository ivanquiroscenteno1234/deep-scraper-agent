"""
MCP Browser Adapter - Wraps MCP client to provide browser-like interface.

This adapter works with the ExecuteAutomation Playwright MCP server
to provide browser automation with native codegen capabilities.

See .agent/workflows/project-specification.md for workflow details.
"""

import asyncio
from typing import Any, Dict, Optional, Tuple
import os

from .mcp_client import PlaywrightMCPClient, get_mcp_client, reset_mcp_client


class MCPBrowserAdapter:
    """
    Adapter that provides browser control using MCP.
    
    Core functionality per project-specification:
    - Navigate to URLs
    - Click elements
    - Fill forms
    - Record steps via codegen
    - Get page HTML for LLM analysis
    """
    
    def __init__(self, use_codegen: bool = True):
        """
        Initialize the MCP browser adapter.
        
        Args:
            use_codegen: If True, automatically start a codegen session
        """
        self.mcp: Optional[PlaywrightMCPClient] = None
        self.use_codegen = use_codegen
        self._launched = False
        self._codegen_started = False
        self._codegen_session_id: Optional[str] = None
        self._output_path: Optional[str] = None
        self._script_prefix: Optional[str] = None
        self._current_url: Optional[str] = None
    
    async def launch(self) -> bool:
        """
        Launch the browser via MCP.
        
        Returns:
            True if MCP server is available and ready
        """
        self.mcp = get_mcp_client()
        
        # Check if MCP server port is available
        is_running = await self.mcp.is_server_running()
        if not is_running:
            print("⚠️ MCP server not running. Please start with:")
            print("   npx @executeautomation/playwright-mcp-server --port 8931")
            return False
        
        # Connect to the MCP server
        connected = await self.mcp.connect()
        if not connected:
            print("⚠️ Failed to connect to MCP server")
            return False
        
        self._launched = True
        print("✅ MCP Browser connected")
        return True
    

    async def start_codegen_session(self, output_path: str, script_prefix: str = "scraper") -> bool:
        """
        Start a codegen session to record actions.
        
        Args:
            output_path: Directory to save generated scripts
            script_prefix: Prefix for generated script names
        """
        if not self._launched:
            if not await self.launch():
                return False
        
        self._output_path = output_path
        self._script_prefix = script_prefix
        
        try:
            session_id = await self.mcp.start_codegen_session(output_path, script_prefix)
            if session_id:
                self._codegen_started = True
                self._codegen_session_id = session_id
                print(f"🎬 Codegen session started: {script_prefix}")
                return True
            return False
        except Exception as e:
            print(f"⚠️ Failed to start codegen session: {e}")
            return False
    
    async def end_codegen_session(self) -> Tuple[bool, Optional[str]]:
        """
        End the codegen session and get the generated script.
        
        Returns:
            Tuple of (success, script_data_json)
        """
        if not self._codegen_started:
            return False, None
        
        try:
            result = await self.mcp.end_codegen_session()
            self._codegen_started = False
            
            result_text = result.get("result", "")
            print(f"✅ Codegen session ended, test file generated")
            return True, result_text
        except Exception as e:
            print(f"❌ Failed to end codegen session: {e}")
            return False, None
    
    async def goto(self, url: str) -> str:
        """Navigate to a URL and return page content."""
        if not self._launched:
            await self.launch()
        
        await self.mcp.navigate(url)
        self._current_url = url
        
        # Wait for page to load
        await asyncio.sleep(1)
        
        return await self.get_clean_content()
    
    async def get_clean_content(self) -> str:
        """Get the page content as text."""
        if not self.mcp:
            return ""
        
        try:
            snapshot = await self.mcp.get_snapshot()
            
            if isinstance(snapshot, dict):
                content = snapshot.get("content") or snapshot.get("text") or ""
                if isinstance(content, list):
                    return "\n".join(str(item) for item in content)
                return str(content)
            return str(snapshot)
        except Exception as e:
            print(f"⚠️ Failed to get content: {e}")
            return ""
    
    async def get_snapshot(self) -> Dict[str, Any]:
        """
        Get page HTML and text for LLM analysis.
        
        Uses playwright_evaluate via client methods to get robust DOM content.
        """
        if not self.mcp:
            return {}
        
        try:
            # Concurrently fetch HTML and text content for efficiency
            html_result, text_result = await asyncio.gather(
                self.mcp.get_html(),
                self.mcp.get_snapshot()
            )
            html_content = html_result.get("result", "")
            text_content = text_result.get("result", "")
            
            return {
                "html": html_content,
                "text": text_content,
                "result": html_content,  # Default for analysis
            }
        except Exception as e:
            print(f"⚠️ Failed to get snapshot: {e}")
            return {}
    
    async def click_element(self, selector: str, description: str = "") -> bool:
        """
        Click an element using a CSS selector.
        
        Args:
            selector: CSS selector for the element
            description: Human-readable description for logging
        """
        if not self.mcp:
            return False
        
        try:
            await self.mcp.click(selector, description)
            await asyncio.sleep(0.5)  # Brief wait after click
            return True
        except Exception as e:
            print(f"❌ Click failed on {selector}: {e}")
            return False
    
    async def fill_form(self, selector: str, value: str, description: str = "") -> bool:
        """
        Fill an input field using a CSS selector.
        
        Args:
            selector: CSS selector for the element
            value: Value to fill
            description: Human-readable description for logging
        """
        if not self.mcp:
            return False
        
        try:
            await self.mcp.fill(selector, value, description or selector)
            return True
        except Exception as e:
            print(f"❌ Fill failed on {selector}: {e}")
            return False
    
    async def press_key(self, key: str) -> bool:
        """Press a keyboard key."""
        if not self.mcp:
            return False
        
        try:
            await self.mcp.press_key(key)
            return True
        except Exception as e:
            print(f"❌ Press key failed: {e}")
            return False

    async def evaluate(self, script: str) -> Any:
        """Execute JavaScript on the page."""
        if not self.mcp:
            return None
        
        try:
            result = await self.mcp.call_tool("playwright_evaluate", {"script": script})
            if isinstance(result, dict):
                return result.get("result")
            return result
        except Exception as e:
            print(f"❌ Evaluate failed: {e}")
            return None
    
    async def screenshot(self, path: str = None) -> Optional[bytes]:
        """Take a screenshot."""
        if not self.mcp:
            return None
        
        try:
            result = await self.mcp.screenshot(full_page=False)
            if isinstance(result, dict) and "data" in result:
                import base64
                return base64.b64decode(result["data"])
            return None
        except Exception as e:
            print(f"⚠️ Screenshot failed: {e}")
            return None
    
    async def wait_for_grid(self, selectors: list, timeout: int = 8000) -> bool:
        """
        Wait for results grid to appear.
        
        Optimization:
        - Pre-processes selectors outside the polling loop
        - Fetches only HTML (no text content) to reduce overhead
        - Reduces MCP roundtrips by 50%

        Args:
            selectors: List of CSS selectors to try (in order of preference)
            timeout: Maximum wait time in milliseconds
            
        Returns:
            True if grid found, False if timeout
        """
        if not self.mcp:
            return False
        
        max_attempts = timeout // 500
        
        # Pre-process selectors once outside the loop
        # We look for the ID/Class string in the HTML
        search_terms = []
        for selector in selectors:
            # Check if selector pattern appears in HTML
            # e.g. "#RsltsGrid" -> "RsltsGrid"
            term = selector.replace("#", "").replace(".", "").split()[0]
            if term:
                search_terms.append(term)

        for _ in range(max_attempts):
            # BOLT ⚡: Optimization - Only fetch HTML, skip text snapshot
            # This reduces overhead since we only need to check for element existence
            html_result = await self.mcp.get_html()
            html = html_result.get("result", "")
            
            for term in search_terms:
                if term in html:
                    return True
            
            await asyncio.sleep(0.5)
        
        return False
    
    async def close(self):
        """Close the browser and cleanup."""
        if self.mcp:
            try:
                if self._codegen_started:
                    await self.end_codegen_session()
                
                # Explicitly close the browser via MCP to clear cookies/state
                try:
                    await self.mcp.close()
                    print("🔒 Browser closed via MCP")
                except Exception as e:
                    print(f"⚠️ Browser close warning: {e}")
                
                await self.mcp.disconnect()
            except Exception:
                pass
        
        self._launched = False
        self._codegen_started = False
        self._current_url = None
    
    async def reset(self):
        """Full reset - close browser, disconnect, and reset singleton."""
        await self.close()
        # Reset the underlying client too
        from .mcp_client import reset_mcp_client
        await reset_mcp_client()
        self.mcp = None
        print("🔄 Browser adapter fully reset")


# Global adapter instance
_mcp_adapter: Optional[MCPBrowserAdapter] = None


def get_mcp_adapter(use_codegen: bool = True) -> MCPBrowserAdapter:
    """Get or create the MCP adapter singleton."""
    global _mcp_adapter
    if _mcp_adapter is None:
        _mcp_adapter = MCPBrowserAdapter(use_codegen=use_codegen)
    return _mcp_adapter


def reset_mcp_adapter():
    """Reset the global adapter instance."""
    global _mcp_adapter
    _mcp_adapter = None


async def is_mcp_available() -> bool:
    """Check if MCP server is available."""
    client = get_mcp_client()
    return await client.is_server_running()
