import asyncio
import copy
import json
import os
from pathlib import Path
from typing import Dict, Optional

class SelectorRegistry:
    """
    Persists discovered selectors per county site to a JSON file.
    This allows the agent to skip exploration on subsequent runs.
    """
    
    def __init__(self, registry_path: str = "output/selector_registry.json", _skip_load: bool = False):
        self.path = Path(registry_path)
        self._lock: Optional[asyncio.Lock] = None
        if not _skip_load:
            self.registry = self._load()
        else:
            self.registry = {}

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @classmethod
    async def acreate(cls, registry_path: str = "output/selector_registry.json") -> "SelectorRegistry":
        """Async factory for instantiating the registry without blocking."""
        instance = cls(registry_path=registry_path, _skip_load=True)
        instance.registry = await instance._aload()
        return instance
    
    def get(self, county: str, element: str) -> Optional[str]:
        """Returns the selector for a specific element in a county."""
        return self.registry.get(county, {}).get(element)
    
    def set(self, county: str, element: str, selector: str):
        """Saves a selector for a specific element in a county."""
        if county not in self.registry:
            self.registry[county] = {}
        self.registry[county][element] = selector
        self._save()

    async def aset(self, county: str, element: str, selector: str):
        """Async saving of a selector for a specific element in a county."""
        async with self.lock:
            if county not in self.registry:
                self.registry[county] = {}
            self.registry[county][element] = selector
            await self._asave()
    
    def _load(self) -> Dict[str, Dict[str, str]]:
        """Loads the registry from the JSON file."""
        if not self.path.exists():
            return {}
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load selector registry: {e}")
            return {}
    
    async def _aload(self) -> Dict[str, Dict[str, str]]:
        """Async variant of loading the registry."""
        return await asyncio.to_thread(self._load)

    def _save(self):
        """Saves the registry to the JSON file."""
        self._save_data(self.registry)

    def _save_data(self, data: Dict[str, Dict[str, str]]):
        """Helper to save a specific dictionary to the JSON file."""
        try:
            # Ensure the directory exists
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save selector registry: {e}")

    async def _asave(self):
        """Async variant of saving the registry."""
        # Deepcopy the registry inside the lock before offloading to a thread.
        # This prevents the 'dictionary changed size during iteration' error
        # and avoids race conditions if the main thread modifies the registry concurrently.
        registry_snapshot = copy.deepcopy(self.registry)
        await asyncio.to_thread(self._save_data, registry_snapshot)
