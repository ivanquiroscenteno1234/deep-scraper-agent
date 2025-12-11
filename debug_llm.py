from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()

class TestSchema(BaseModel):
    reason: str = Field(description="Reasoning")

try:
    print("Initializing LLM...")
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    print("LLM Initialized.")

    print("Configuring structured output...")
    structured_llm = llm.with_structured_output(TestSchema)
    print("Structured LLM Configured.")

    print("Invoking...")
    res = structured_llm.invoke("Why is the sky blue?")
    print(f"Result: {res}")

except Exception as e:
    print(f"Error: {e}")
