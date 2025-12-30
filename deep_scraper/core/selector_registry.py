import json
import os
from pathlib import Path
from typing import Dict, Optional

class SelectorRegistry:
    """
    Persists discovered selectors per county site to a JSON file.
    This allows the agent to skip exploration on subsequent runs.
    """
    
    def __init__(self, registry_path: str = "output/selector_registry.json"):
        self.path = Path(registry_path)
        self.registry = self._load()
    
    def get(self, county: str, element: str) -> Optional[str]:
        """Returns the selector for a specific element in a county."""
        return self.registry.get(county, {}).get(element)
    
    def set(self, county: str, element: str, selector: str):
        """Saves a selector for a specific element in a county."""
        if county not in self.registry:
            self.registry[county] = {}
        self.registry[county][element] = selector
        self._save()
    
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
    
    def _save(self):
        """Saves the registry to the JSON file."""
        try:
            # Ensure the directory exists
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save selector registry: {e}")
