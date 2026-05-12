from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import keyboard


@dataclass
class HotkeyConfig:
    start: str = "f1"
    pause: str = "f2"
    stop: str = "f3"


class GlobalHotkeys:
    def __init__(
        self,
        config: HotkeyConfig,
        on_start: Callable[[], None],
        on_pause: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        self.config = config
        self._handles: list[int] = []
        self._on_start = on_start
        self._on_pause = on_pause
        self._on_stop = on_stop

    def register(self) -> None:
        self._handles.append(keyboard.add_hotkey(self.config.start, self._on_start))
        self._handles.append(keyboard.add_hotkey(self.config.pause, self._on_pause))
        self._handles.append(keyboard.add_hotkey(self.config.stop, self._on_stop))

    def unregister(self) -> None:
        for handle in self._handles:
            keyboard.remove_hotkey(handle)
        self._handles.clear()
