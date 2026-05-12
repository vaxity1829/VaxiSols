from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


class PluginLoader:
    def __init__(self, plugin_dir: Path) -> None:
        self.plugin_dir = plugin_dir
        self.plugins: dict[str, Any] = {}

    def discover(self) -> dict[str, str]:
        statuses: dict[str, str] = {}
        self.plugins.clear()
        if not self.plugin_dir.exists():
            return statuses

        for entry in self.plugin_dir.glob("*.py"):
            module_name = f"vaxisols_plugin_{entry.stem}"
            spec = importlib.util.spec_from_file_location(module_name, entry)
            if not spec or not spec.loader:
                statuses[entry.name] = "failed: missing loader"
                continue
            try:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.plugins[entry.stem] = module
                statuses[entry.name] = "loaded"
            except Exception as exc:
                statuses[entry.name] = f"failed: {exc}"
        return statuses

    def run_hook(self, hook_name: str, payload: dict[str, Any]) -> None:
        for module in self.plugins.values():
            hook = getattr(module, hook_name, None)
            if callable(hook):
                try:
                    hook(payload)
                except Exception:
                    continue
