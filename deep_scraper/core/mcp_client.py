"""
Playwright MCP Client - Using ExecuteAutomation MCP Server.

This client uses the ExecuteAutomation Playwright MCP server which provides
native codegen tools for script generation.

MCP Server: @executeautomation/playwright-mcp-server
"""

import asyncio
import socket
from typing import Any, Dict, List, Optional, Tuple
from contextlib import asynccontextmanager

# Official MCP SDK imports
from mcp import ClientSession
from mcp.client.sse import sse_client


class PlaywrightMCPClient:
    """
    Client for ExecuteAutomation Playwright MCP server.
    
    This server provides native codegen tools:
    - start_codegen_session
    - end_codegen_session
    - get_codegen_session
    - clear_codegen_session
    """
    
    def __init__(self, port: int = 8931):
        """
        Initialize MCP client.
        
        Args:
            port: MCP server port (default 8931 for ExecuteAutomation HTTP mode)
        """
        self.port = port
        self.base_url = f"http://localhost:{port}/sse"  # SSE endpoint
        self._session: Optional[ClientSession] = None
        self._read_stream = None
        self._write_stream = None
        self._context_manager = None
        self._session_context = None
        self._codegen_active = False
        self._codegen_session_id: Optional[str] = None
    
    async def is_server_running(self) -> bool:
        """Check if the MCP server is running by testing the port."""
        # Bolt ⚡: Use asyncio.open_connection to prevent blocking the event loop
        # Try IPv6 first
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection('::1', self.port),
                timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError, ConnectionRefusedError):
            pass

        # Fallback to IPv4
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection('127.0.0.1', self.port),
                timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError, ConnectionRefusedError):
            return False
    
    async def connect(self) -> bool:
        """
        Connect to the MCP server using streamable HTTP transport.
        
        Returns:
            True if connection successful
        """
        if self._session is not None:
            return True
        
        try:
            # Create the SSE client context (ExecuteAutomation uses SSE transport)
            self._context_manager = sse_client(self.base_url)
            streams = await self._context_manager.__aenter__()
            self._read_stream, self._write_stream = streams
            
            # Create and initialize the session
            self._session_context = ClientSession(self._read_stream, self._write_stream)
            self._session = await self._session_context.__aenter__()
            
            # Initialize the MCP connection
            await self._session.initialize()
            
            print("✅ Connected to ExecuteAutomation MCP server")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to connect to MCP server: {e}")
            await self.disconnect()
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        print("🔌 Disconnecting from MCP server...")
        self._session = None
        self._session_context = None
        self._context_manager = None
        self._read_stream = None
        self._write_stream = None
        self._codegen_session_id = None
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any] = None) -> Any:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the MCP tool
            params: Parameters for the tool
            
        Returns:
            Result from the MCP tool
        """
        if self._session is None:
            if not await self.connect():
                raise Exception("Not connected to MCP server")
        
        if params is None:
            params = {}
        
        try:
            result = await self._session.call_tool(tool_name, arguments=params)
            
            # Extract content from result - some tools return multiple TextContent items
            if result and result.content:
                text_parts = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        text_parts.append(content.text)
                
                if text_parts:
                    # If it's Playwright evaluate, it often returns ["Executed JavaScript:", "script", "Result:", "actual_result"]
                    if tool_name == "playwright_evaluate" and len(text_parts) >= 4 and text_parts[2] == "Result:":
                        val = text_parts[3].strip()
                        # Some versions return a quoted string
                        if val.startswith('"') and val.endswith('"'):
                            val = val[1:-1].replace('\\n', '\n').replace('\\"', '"')
                        return {"result": val}
                    
                    # Fallback: join all text parts
                    full_text = "\n".join(text_parts)
                    return {"result": full_text}
                
                return {"result": str(result.content)}
            return {"result": None}
            
        except Exception as e:
            raise Exception(f"MCP tool '{tool_name}' failed: {e}")
    
    async def list_tools(self) -> List[str]:
        """List available MCP tools."""
        if self._session is None:
            if not await self.connect():
                return []
        
        try:
            tools = await self._session.list_tools()
            return [tool.name for tool in tools.tools]
        except Exception as e:
            print(f"⚠️ Failed to list tools: {e}")
            return []
    
    # ============ Codegen Session Tools ============
    
    async def start_codegen_session(self, output_path: str, test_name_prefix: str = "scraper") -> Optional[str]:
        """
        Start a code generation session.
        
        Args:
            output_path: Absolute path to directory for generated scripts
            test_name_prefix: Prefix for generated test names
            
        Returns:
            Session ID for the codegen session
        """
        print(f"🎬 Starting codegen session: {test_name_prefix}")
        
        try:
            result = await self.call_tool("start_codegen_session", {
                "options": {
                    "outputPath": output_path,
                    "testNamePrefix": test_name_prefix,
                    "includeComments": True
                }
            })
            
            # Extract session ID from result
            result_text = result.get("result", "")
            if result_text:
                # Parse JSON if it's a JSON string containing sessionId
                import json
                try:
                    if isinstance(result_text, str):
                        data = json.loads(result_text)
                        if isinstance(data, dict) and "sessionId" in data:
                            self._codegen_session_id = data["sessionId"]
                        else:
                            self._codegen_session_id = result_text.strip()
                    else:
                        self._codegen_session_id = str(result_text)
                except json.JSONDecodeError:
                    self._codegen_session_id = result_text.strip()
                
                self._codegen_active = True
                print(f"🎬 Codegen session started: {self._codegen_session_id}")
                return self._codegen_session_id
            
            self._codegen_active = True
            print(f"✅ Codegen session started (no session ID returned)")
            return "active"
            
        except Exception as e:
            print(f"⚠️ Failed to start codegen session: {e}")
            return None
    
    async def end_codegen_session(self, session_id: str = None) -> Dict[str, Any]:
        """
        End the codegen session and get the generated script.
        
        Args:
            session_id: Session ID (uses stored ID if not provided)
            
        Returns:
            Information about the generated test file
        """
        if not self._codegen_active:
            return {}
        
        sid = session_id or self._codegen_session_id
        print(f"🎬 Ending codegen session: {sid}")
        
        try:
            result = await self.call_tool("end_codegen_session", {
                "sessionId": sid
            })
            
            self._codegen_active = False
            self._codegen_session_id = None
            
            print(f"✅ Codegen session ended, test file generated")
            return result
            
        except Exception as e:
            print(f"⚠️ Failed to end codegen session: {e}")
            self._codegen_active = False
            return {}
    
    async def get_codegen_session(self, session_id: str = None) -> Dict[str, Any]:
        """Get information about a codegen session."""
        sid = session_id or self._codegen_session_id
        if not sid:
            return {}
        
        try:
            return await self.call_tool("get_codegen_session", {"sessionId": sid})
        except Exception as e:
            print(f"⚠️ Failed to get codegen session: {e}")
            return {}
    
    # ============ Browser Automation Tools ============
    # Note: ExecuteAutomation uses Playwright_* naming convention
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        print(f"🌐 Navigating to: {url}")
        return await self.call_tool("playwright_navigate", {"url": url})
    
    async def click(self, selector: str, description: str = "") -> Dict[str, Any]:
        """Click an element by selector."""
        print(f"🖱️ Clicking: {description or selector}")
        return await self.call_tool("playwright_click", {"selector": selector})
    
    async def fill(self, selector: str, value: str, description: str = "") -> Dict[str, Any]:
        """Fill a text field."""
        print(f"⌨️ Filling: {description or selector}")
        return await self.call_tool("playwright_fill", {"selector": selector, "value": value})
    
    async def get_snapshot(self) -> Dict[str, Any]:
        """Get visible text of the page using JS evaluation."""
        return await self.call_tool("playwright_evaluate", {"script": "document.body.innerText"})
    
    async def get_html(self) -> Dict[str, Any]:
        """Get visible HTML of the page using JS evaluation."""
        return await self.call_tool("playwright_evaluate", {"script": "document.documentElement.outerHTML"})

    async def get_cleaned_html(self) -> Dict[str, Any]:
        """
        Get the cleaned HTML of the page (removing scripts, styles, etc) using JS evaluation.

        Bolt ⚡ Optimization:
        - Performs HTML cleaning in the browser to reduce network payload size by 90%+
        - Avoids expensive regex processing in Python
        """
        script = """
        (function() {
            const clone = document.documentElement.cloneNode(true);

            // Helper to remove elements
            const remove = (sel) => {
                const elements = clone.querySelectorAll(sel);
                for (const el of elements) {
                    el.remove();
                }
            };

            // Remove noisy tags
            remove('script, style, link, svg, noscript, iframe, object, embed, template');

            // Remove comments (using TreeWalker)
            const walker = document.createTreeWalker(clone, NodeFilter.SHOW_COMMENT);
            const comments = [];
            while(walker.nextNode()) comments.push(walker.currentNode);
            for (const c of comments) {
                if (c.parentNode) c.parentNode.removeChild(c);
            }

            // Remove elements with inline hidden styles
            // Note: We iterate all elements in the clone. fast enough for detached DOM.
            const allElements = clone.querySelectorAll('*');
            for (const el of allElements) {
                if (el.style.display === 'none' || el.style.visibility === 'hidden') {
                    el.remove();
                }
            }

            return clone.outerHTML;
        })()
        """
        # Minify script slightly to be safe (remove newlines/indentation)
        script = " ".join(line.strip() for line in script.splitlines() if line.strip())

        return await self.call_tool("playwright_evaluate", {"script": script})

    async def get_full_page_content(self) -> Dict[str, Any]:
        """
        Get both HTML and text content in a single call.

        Bolt ⚡ Optimization:
        - Reduces MCP network roundtrips by 50%
        - Fetches both DOM and Text in one JS execution
        """
        script = "JSON.stringify({html: document.documentElement.outerHTML, text: document.body.innerText})"
        return await self.call_tool("playwright_evaluate", {"script": script})
    
    async def screenshot(self, name: str = "screenshot", full_page: bool = False) -> Dict[str, Any]:
        """Take a screenshot of the page."""
        return await self.call_tool("playwright_screenshot", {"name": name, "fullPage": full_page})
    
    async def press_key(self, key: str) -> Dict[str, Any]:
        """Press a keyboard key."""
        return await self.call_tool("playwright_press_key", {"key": key})
    
    async def close(self) -> Dict[str, Any]:
        """Close the browser."""
        return await self.call_tool("playwright_close", {})


# Singleton instance
_mcp_client: Optional[PlaywrightMCPClient] = None


def get_mcp_client(port: int = 8931) -> PlaywrightMCPClient:
    """Get or create the singleton MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = PlaywrightMCPClient(port)
    return _mcp_client


async def reset_mcp_client():
    """Reset the MCP client (disconnect and clear singleton)."""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.disconnect()
        _mcp_client = None
