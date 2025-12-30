import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def list_tools():
    async with sse_client('http://localhost:8931/sse') as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"Total tools: {len(tools.tools)}")
            print("="*50)
            for t in tools.tools:
                if 'codegen' in t.name.lower():
                    print(f"🎬 {t.name}")
                else:
                    print(f"   {t.name}")

asyncio.run(list_tools())




