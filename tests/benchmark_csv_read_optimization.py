import asyncio
import time
import os
import csv
from threading import Timer

def read_sync():
    time.sleep(0.5) # Simulate IO
    try:
        with open("test_large.csv", "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["col1", "col2", "col3"])
            for i in range(100000):
                writer.writerow([f"val1_{i}", f"val2_{i}", f"val3_{i}"])

        with open("test_large.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader), "test_large.csv"
    except Exception as e:
        return [], None
    finally:
        if os.path.exists("test_large.csv"):
            os.remove("test_large.csv")

async def event_loop_ticker(stop_event):
    ticks = 0
    while not stop_event.is_set():
        await asyncio.sleep(0.001)
        ticks += 1
    return ticks

class AsyncStopEvent:
    def __init__(self):
        self._flag = False
    def set(self):
        self._flag = True
    def is_set(self):
        return self._flag

async def main_sync():
    print("Testing Sync (Blocking) Read...")
    stop_event = AsyncStopEvent()
    ticker_task = asyncio.create_task(event_loop_ticker(stop_event))

    start_time = time.time()
    data, path = read_sync()
    stop_event.set()
    read_time = time.time() - start_time

    ticks = await ticker_task
    print(f"Sync Read Time: {read_time:.4f}s")
    print(f"Event Loop Ticks during Sync read: {ticks}")

async def main_async():
    print("\nTesting Async (Non-Blocking) Read...")
    stop_event = AsyncStopEvent()
    ticker_task = asyncio.create_task(event_loop_ticker(stop_event))

    start_time = time.time()
    data, path = await asyncio.to_thread(read_sync)
    stop_event.set()
    read_time = time.time() - start_time

    ticks = await ticker_task
    print(f"Async Read Time: {read_time:.4f}s")
    print(f"Event Loop Ticks during Async read: {ticks}")

async def run():
    await main_sync()
    await main_async()

if __name__ == "__main__":
    asyncio.run(run())
