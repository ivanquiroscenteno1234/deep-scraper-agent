import os
import typing
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage

from prompts import EXPLORER_SYSTEM_PROMPT, CODE_GENERATION_PROMPT

load_dotenv()


class StreamlitLogHandler(BaseCallbackHandler):
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.tool_calls = []  # Track tool usage

    def on_llm_start(self, serialized: typing.Dict[str, typing.Any], prompts: typing.List[str], **kwargs: typing.Any) -> None:
        self.log_callback("🤖 AI is thinking...")

    def on_tool_start(self, serialized: typing.Dict[str, typing.Any], input_str: str, **kwargs: typing.Any) -> None:
        tool_name = serialized.get('name', 'unknown') if serialized else 'unknown'
        self.tool_calls.append(tool_name)
        self.log_callback(f"🛠️ Using tool: {tool_name}")

    def on_agent_action(self, action, **kwargs: typing.Any) -> None:
        self.log_callback(f"⚡ Action: {action.tool} - {str(action.tool_input)[:100]}...")

    def on_tool_end(self, output: str, **kwargs: typing.Any) -> None:
        output_str = str(output) if output else ""
        preview = output_str[:150] + "..." if len(output_str) > 150 else output_str
        self.log_callback(f"✅ Result: {preview}")

    def on_agent_finish(self, finish, **kwargs: typing.Any) -> None:
        self.log_callback(f"🏁 Phase completed. Tool calls made: {len(self.tool_calls)}")


class ScriptExplorer:
    def __init__(self, log_callback):
        self.log_callback = log_callback
        
        # Initialize LLM
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro-latest")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            self.log_callback("⚠️ WARNING: GOOGLE_API_KEY not found!")
        
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=api_key,
        )

    async def explore_async(self, url: str, county_name: str) -> str:
        """
        Two-phase approach:
        1. EXPLORATION: Force the AI to use browser tools to discover page structure
        2. GENERATION: Use the exploration findings to generate code
        """
        self.log_callback(f"🚀 Starting exploration for {county_name}")
        self.log_callback(f"📍 Target URL: {url}")
        
        # Launch browser
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        
        try:
            # Create toolkit
            toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
            tools = toolkit.get_tools()
            tool_names = [t.name for t in tools]
            
            self.log_callback(f"🔧 Available tools: {', '.join(tool_names)}")
            
            # ============== PHASE 1: EXPLORATION ==============
            self.log_callback("\n" + "="*50)
            self.log_callback("📍 PHASE 1: EXPLORATION")
            self.log_callback("="*50)
            
            exploration_handler = StreamlitLogHandler(self.log_callback)
            
            # Force exploration with very specific instructions
            exploration_prompt = ChatPromptTemplate.from_messages([
                ("system", EXPLORER_SYSTEM_PROMPT),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            exploration_agent = create_tool_calling_agent(self.llm, tools, exploration_prompt)
            
            exploration_executor = AgentExecutor(
                agent=exploration_agent, 
                tools=tools, 
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=15,  # Allow more iterations for thorough exploration
                early_stopping_method="generate"
            )
            
            exploration_task = f"""
You are exploring {url} to understand how to search for records.

YOU MUST USE THE BROWSER TOOLS. Do not generate any code yet.

## STEP 1: Navigate
Call navigate_browser with url="{url}"

## STEP 2: Check for Disclaimer Page
Call extract_text to see the page content.
If you see words like "disclaimer", "accept", "agree", "conditions" - this is a disclaimer page.
Call get_elements with selector="input[type='button'], input[type='submit']" to find the accept button.

## STEP 3: Click the Accept/Disclaimer Button
Look at the elements you found. Find one with text like "I accept" or "accept" or "agree".
Call click_element with that selector (e.g., input[value*='accept' i] or the specific selector you found).

## STEP 4: After Clicking Accept, Find the Search Form  
Call get_elements with selector="input[type='text'], input[id*='name' i], input[id*='search' i]"
Call get_elements with selector="input[type='submit'], button"
Report what you find - the IDs and names of each input field.

## STEP 5: Test the Search
Call fill_text on the name input field with the value "TestName"
Call click_element on the search button
Call extract_text to see what happens (results or error message)

## IMPORTANT
- Empty results for inputs/buttons might mean you're still on the disclaimer page
- After clicking accept, call get_elements again to find the actual form
- Report the exact selector for each element (preferring #id format)

At the end, provide:
SUMMARY:
- Disclaimer button selector: [what you found]
- Name input selector: [what you found]
- Search button selector: [what you found]
"""
            
            exploration_result = await exploration_executor.ainvoke(
                {"input": exploration_task},
                config={"callbacks": [exploration_handler]}
            )
            
            exploration_findings = exploration_result.get("output", "")
            tools_used = len(exploration_handler.tool_calls)
            
            self.log_callback(f"\n✅ Exploration complete. Tools used: {tools_used}")
            
            # Check if tools were actually used - need at least 5 for proper exploration
            if tools_used < 5:
                self.log_callback("⚠️ WARNING: Not enough exploration!")
                self.log_callback("Retrying with explicit step-by-step instructions...")
                
                # Retry with very explicit step-by-step instructions
                retry_task = f"""
You need to use more browser tools. Do these steps NOW:

STEP 1: Navigate to the page
Call: navigate_browser(url="{url}")

STEP 2: Read the page
Call: extract_text()

STEP 3: Find buttons (disclaimer or search)
Call: get_elements(selector="input[type='button'], input[type='submit'], button")

STEP 4: If you see a disclaimer page, click the accept button
Call: click_element(selector="input[value*='accept' i]")

STEP 5: After accept, find the search form
Call: get_elements(selector="input[type='text'], input[id*='name' i]")
Call: get_elements(selector="input[type='submit']")

Report ALL selectors you find with their IDs.
"""
                retry_result = await exploration_executor.ainvoke(
                    {"input": retry_task},
                    config={"callbacks": [exploration_handler]}
                )
                exploration_findings = retry_result.get("output", "")
                tools_used = len(exploration_handler.tool_calls)
            
            # ============== PHASE 2: CODE GENERATION ==============
            self.log_callback("\n" + "="*50)
            self.log_callback("📝 PHASE 2: CODE GENERATION")
            self.log_callback("="*50)
            
            # Now generate code based on the exploration findings
            code_generation_task = f"""
Based on your exploration of {url}, write a complete Python Playwright script.

Here's what you discovered during exploration:
{exploration_findings}

The county is: {county_name}

Now write the Python code. The function signature must be:
def search_county(page: Page, builder_name: str) -> list[dict]:

Include:
1. Handling for any disclaimer/accept buttons you found
2. The exact selectors you discovered (use #id where possible)
3. Proper waits (wait_for_selector, wait_for_load_state)
4. Data extraction from the results table
5. Error handling with screenshot capture

Return ONLY the Python code, no explanations.
"""
            
            code_result = await self.llm.ainvoke([HumanMessage(content=code_generation_task)])
            final_code = code_result.content
            
            # Clean up the code
            if "```python" in final_code:
                final_code = final_code.split("```python")[1].split("```")[0]
            elif "```" in final_code:
                final_code = final_code.split("```")[1].split("```")[0]
            
            final_code = final_code.strip()
            
            self.log_callback(f"\n✅ Code generation complete!")
            self.log_callback(f"📊 Total tool calls during exploration: {tools_used}")
            
            return final_code
            
        except Exception as e:
            self.log_callback(f"❌ Error: {e}")
            return f"# Error generating code: {e}"
        finally:
            await browser.close()
            await playwright.stop()

    def explore(self, url: str, county_name: str) -> str:
        """Sync wrapper."""
        return asyncio.run(self.explore_async(url, county_name))
