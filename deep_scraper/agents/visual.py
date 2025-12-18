import os
import asyncio
import base64
import json
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

from playwright.async_api import async_playwright, Page
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from deep_scraper.utils.dom import simplify_dom

from dotenv import load_dotenv

# Define structured output for the Action Decision
load_dotenv()

class VisualAction(BaseModel):
    action_type: Literal['click', 'fill', 'navigate', 'wait', 'finish'] = Field(
        description="The action to take. MUST be one of: 'click', 'fill', 'navigate', 'wait', 'finish'"
    )
    selector: Optional[str] = Field(description="The CSS selector to interact with (for click/fill)")
    value: Optional[str] = Field(description="The value to type (for fill) or URL (for navigate)")
    reasoning: str = Field(description="Brief explanation of why this action was chosen")
    is_disclaimer: bool = Field(default=False, description="True if this action is accepting a disclaimer")

class VisualExplorer:
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.recorded_steps = []
        
        # Initialize Gemini from environment variable
        model_name = os.getenv("GEMINI_MODEL")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=api_key,
            model_kwargs={
                "thinking_config": {
                    "include_thoughts": True,
                    "thinking_level": os.getenv("THINKING_LEVEL")
                }
            }
        )
        
    async def get_b64_screenshot(self, page: Page) -> str:
        screenshot_bytes = await page.screenshot(type="jpeg", quality=70)
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def decide_next_action(self, page: Page, goal: str) -> VisualAction:
        # 1. Capture State
        screenshot_b64 = await self.get_b64_screenshot(page)
        dom_summary = simplify_dom(await page.content())
        
        # 2. Construct Prompt
        system_msg = """
        You are a Visual Web Automation Agent. 
        Your goal is to navigate a website to achieve a specific objective.
        
        You will see:
        1. A screenshot of the current page.
        2. A simplified list of interactive elements (inputs, buttons).
        
        You must decide the NEXT SINGLE ACTION to take.
        
        Rules:
        - If you see a disclaimer/agreement modal, you MUST accept it first.
        - If you are on a search page, find the inputs and search button.
        - Prefer using ID selectors (#id) if available.
        - If the goal is achieved (e.g., results are visible), return action_type='finish'.
        """
        
        user_msg_content = [
            {"type": "text", "text": f"GOAL: {goal}\n\nCURRENT DOM:\n{dom_summary}"},
            {
                "type": "image_url", 
                "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}
            }
        ]
        
        # 3. Call LLM with Structured Output
        structured_llm = self.llm.with_structured_output(VisualAction)
        
        try:
            action = await structured_llm.ainvoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=user_msg_content)
            ])
            return action
        except Exception as e:
            self.log_callback(f"❌ Error getting decision: {e}")
            # Fallback or retry logic could go here
            raise e

    async def execute_action(self, page: Page, action: VisualAction):
        """Executes the chosen action and records it."""
        self.log_callback(f"🤖 Reasoning: {action.reasoning}")
        self.log_callback(f"⚡ Action: {action.action_type} -> {action.selector} {f'({action.value})' if action.value else ''}")
        
        try:
            if action.action_type == 'navigate':
                await page.goto(action.value)
                await page.wait_for_load_state("networkidle")
                
            elif action.action_type == 'click':
                if not action.selector:
                    raise ValueError("Click action requires a selector")
                await page.click(action.selector)
                # Wait a bit for potential navigation/network
                try:
                    await page.wait_for_load_state("networkidle", timeout=2000)
                except:
                    pass # Ignore timeout on wait
                    
            elif action.action_type == 'fill':
                if not action.selector or action.value is None:
                    raise ValueError("Fill action requires selector and value")
                await page.fill(action.selector, action.value)
                
            elif action.action_type == 'wait':
                await asyncio.sleep(2)
                
            elif action.action_type == 'finish':
                return "FINISHED"
                
            # Record successful action
            self.recorded_steps.append(action.dict())
            return "CONTINUE"
            
        except Exception as e:
            self.log_callback(f"⚠️ Action failed: {e}")
            return "ERROR"

    async def run_loop(self, url: str, goal: str, max_steps=10):
        self.log_callback(f"🚀 Starting Visual Recorder...")
        self.log_callback(f"🎯 Goal: {goal}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            # Initial navigation
            await page.set_viewport_size({"width": 1280, "height": 720})
            
            # Manually trigger first nav to start the loop at the right place
            await page.goto(url)
            self.recorded_steps.append({
                "action_type": "navigate",
                "value": url,
                "reasoning": "Initial navigation"
            })
            
            step_count = 0
            while step_count < max_steps:
                self.log_callback(f"\n--- Step {step_count + 1} ---")
                
                # 1. Decide
                action = await self.decide_next_action(page, goal)
                
                # 2. Execute
                result = await self.execute_action(page, action)
                
                if result == "FINISHED":
                    self.log_callback("🏁 Goal achieved!")
                    break
                elif result == "ERROR":
                    self.log_callback("🛑 Stopping due to error.")
                    break
                    
                step_count += 1
                await asyncio.sleep(1) # Brief pause
                
            await browser.close()
            
        return self.recorded_steps
