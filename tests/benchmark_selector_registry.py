import asyncio
import time
import json
import os
from pathlib import Path

from deep_scraper.core.selector_registry import SelectorRegistry

async def measure_event_loop_ticks(duration=0.5):
    """Counts how many times the event loop ticks in a given duration."""
    ticks = 0
    start = time.perf_counter()
    while time.perf_counter() - start < duration:
        ticks += 1
        await asyncio.sleep(0)
    return ticks

async def run_baseline():
    print("Preparing large registry file...")
    test_file = "output/test_registry.json"

    # Create an extremely large dummy dictionary to exacerbate blocking
    # Increased sizes by 10x to ensure we see a real event loop drop
    dummy_data = {f"county_{i}": {f"element_{j}": f"#selector_{i}_{j}" for j in range(1000)} for i in range(1000)}
    Path("output").mkdir(exist_ok=True)
    with open(test_file, "w") as f:
        json.dump(dummy_data, f)

    file_size_mb = os.path.getsize(test_file) / (1024 * 1024)
    print(f"Test file size: {file_size_mb:.2f} MB")

    print("\n--- SYNCHRONOUS (BLOCKING) RUN ---")

    tick_task_sync = asyncio.create_task(measure_event_loop_ticks(2.0))
    await asyncio.sleep(0.1)

    start_time_sync = time.perf_counter()
    # Synchronous initialization and saving block the event loop
    registry = SelectorRegistry(registry_path=test_file)
    registry.set("county_0", "element_0", "#new_selector")
    sync_duration = time.perf_counter() - start_time_sync

    print(f"Sync operation took: {sync_duration:.4f} seconds")

    ticks_sync = await tick_task_sync
    print(f"Event loop ticks during 2s window: {ticks_sync}")

    print("\n--- ASYNCHRONOUS (NON-BLOCKING) RUN ---")
    tick_task_async = asyncio.create_task(measure_event_loop_ticks(2.0))
    await asyncio.sleep(0.1)

    start_time_async = time.perf_counter()
    if hasattr(SelectorRegistry, 'acreate'):
        registry_async = await SelectorRegistry.acreate(registry_path=test_file)
        await registry_async.aset("county_0", "element_0", "#new_selector")
    else:
        print("Async methods not yet implemented. Simulating with sync methods.")
        # We simulate what it would look like if it were just standard to keep test runnable
        registry_async = SelectorRegistry(registry_path=test_file)
        registry_async.set("county_0", "element_0", "#new_selector")

    async_duration = time.perf_counter() - start_time_async
    print(f"Async operation took: {async_duration:.4f} seconds")

    ticks_async = await tick_task_async
    print(f"Event loop ticks during 2s window: {ticks_async}")

    # Clean up
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    asyncio.run(run_baseline())
