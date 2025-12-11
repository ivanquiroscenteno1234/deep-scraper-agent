import langchain
import langchain.agents
import sys

print(f"LangChain version: {langchain.__version__}")
print(f"LangChain path: {langchain.__path__}")

try:
    from langchain.agents import AgentExecutor
    print("SUCCESS: AgentExecutor found in langchain.agents")
except ImportError as e:
    print(f"ERROR: {e}")
    print("Contents of langchain.agents:")
    print(dir(langchain.agents))
    
    # Try alternate location
    try:
        from langchain.agents.agent import AgentExecutor
        print("SUCCESS: AgentExecutor found in langchain.agents.agent")
    except ImportError:
        print("ERROR: AgentExecutor not found in langchain.agents.agent either")

try:
    from langchain.agents import create_tool_calling_agent
    print("SUCCESS: create_tool_calling_agent found")
except ImportError:
    print("ERROR: create_tool_calling_agent not found")
