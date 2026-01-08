import pytest
import asyncio
import time
import httpx
from datetime import datetime

# URL of the running server
BASE_URL = "http://localhost:8006"

async def check_health(client):
    """Checks the health endpoint."""
    start = time.time()
    try:
        response = await client.get(f"{BASE_URL}/health", timeout=5.0)
        end = time.time()
        return end - start, response.status_code
    except httpx.TimeoutException:
        return 5.0, 504

async def run_blocking_script(client):
    """Calls the endpoint that executes a blocking script."""
    # Create a dummy request matching ExecuteRequest schema
    # IMPORTANT: The server runs with CWD=backend, so script path should be relative to that
    payload = {
        "script_path": "sleep_script.py",
        "search_query": "test",
        "start_date": "01/01/2020",
        "end_date": "01/01/2021"
    }
    start = time.time()
    try:
        response = await client.post(f"{BASE_URL}/api/execute-script", json=payload, timeout=10.0)
        end = time.time()
        return end - start, response.status_code
    except httpx.TimeoutException:
         return 10.0, 504

@pytest.mark.asyncio
async def test_concurrency():
    """
    Tests if the execute-script endpoint blocks other requests.
    It runs the blocking script and immediately tries to access /health.
    If /health waits for the script to finish, the server is blocking.
    """
    async with httpx.AsyncClient() as client:
        # Start the blocking request
        print(f"\n[{datetime.now().time()}] Starting blocking request...")
        blocking_task = asyncio.create_task(run_blocking_script(client))

        # Wait a tiny bit to ensure the request has hit the server and started processing
        await asyncio.sleep(0.5)

        # Start the health check
        print(f"[{datetime.now().time()}] Starting health check...")
        health_duration, health_status = await check_health(client)
        print(f"[{datetime.now().time()}] Health check finished in {health_duration:.4f}s")

        # Wait for blocking task
        script_duration, script_status = await blocking_task
        print(f"[{datetime.now().time()}] Script finished in {script_duration:.4f}s")

        # Assertion logic
        if health_duration > 1.0:
             print("FAIL: Health check was blocked!")
        else:
             print("SUCCESS: Health check was NOT blocked.")

        # The core test: health check should be fast (< 0.5s) even if script takes 2s
        # If it takes long, it means it was blocked.
        assert health_duration < 1.0, f"Health check took too long: {health_duration:.4f}s - Server is likely blocking!"
