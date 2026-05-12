from __future__ import annotations

import ctypes
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any

import webview

from core.biome_detector import BiomeDetector


def _bundle_root() -> Path:
    """Directory containing bundled assets (ui/, icons/). PyInstaller onefile uses _MEIPASS."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


ROOT_DIR = _bundle_root()
UI_FILE = ROOT_DIR / "ui" / "index.html"
ICON_PNG = ROOT_DIR / "VaxiSolsIcon.png"
ICON_ICO = ROOT_DIR / "VaxiSolsIcon.ico"
WINDOW_ICON = ICON_ICO if ICON_ICO.exists() else ICON_PNG

# Portable config path - save in same directory as executable
def get_config_path() -> Path:
    """Get config path for portable mode (same directory as exe)."""
    # Try to get the directory where the executable is located
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        exe_dir = Path(sys.executable).resolve().parent
    else:
        # Running as script
        exe_dir = Path(__file__).resolve().parent
    
    # Create config directory in exe location
    config_dir = exe_dir / "config"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "default.json"


class VaxiSolsApi:
    def __init__(self, detector: BiomeDetector) -> None:
        self.detector = detector

    def get_state(self) -> dict[str, Any]:
        return self.detector.snapshot()

    def start_detector(self) -> dict[str, Any]:
        self.detector.start()
        return self.get_state()

    def stop_detector(self) -> dict[str, Any]:
        self.detector.stop()
        return self.get_state()

    def add_account(self, username: str) -> dict[str, Any]:
        return self.detector.add_account(username)

    def remove_account(self, username: str) -> dict[str, Any]:
        return self.detector.remove_account(username)

    def get_roblox_windows(self) -> list[dict[str, Any]]:
        return self.detector.get_roblox_windows()

    def set_account_window(self, username: str, hwnd: int) -> dict[str, Any]:
        return self.detector.set_account_window(username, hwnd)

    def minimize_window(self) -> dict[str, Any]:
        """Minimize pywebview window with animation."""
        try:
            for w in webview.windows:
                # Try to minimize with animation
                w.minimize()
                break
        except Exception:
            pass
        return {"ok": True}

    def close_window(self) -> dict[str, Any]:
        """Close pywebview window."""
        try:
            import webview
            # Find and destroy the window
            for window in webview.windows:
                window.destroy()
                break
        except Exception:
            pass
        return {"ok": True}

    def maximize_window(self) -> dict[str, Any]:
        """Toggle maximize/restore the pywebview window."""
        try:
            for w in webview.windows:
                w.toggle_fullscreen()
                break
        except Exception:
            pass
        return {"ok": True}

    def pick_window(self) -> dict[str, Any]:
        """Open window picker to select Roblox window by clicking."""
        return self.detector.pick_window()

    def load_config(self) -> dict[str, Any]:
        config_path = get_config_path()
        if not config_path.exists():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save_webhooks(self, urls: list[str], private_server: str = "") -> dict[str, Any]:
        config_path = get_config_path()
        data: dict[str, Any] = {}
        if config_path.exists():
            try:
                raw = config_path.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
            except (json.JSONDecodeError, OSError):
                pass
        data["webhooks"] = {"urls": [u.strip() for u in urls if u.strip()]}
        if private_server.strip():
            data["private_server"] = private_server.strip()
        elif "private_server" in data:
            del data["private_server"]
        
        tmp = config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(config_path)
        self.detector.load_config()
        return {"ok": True}

    def test_webhook(self) -> dict[str, Any]:
        return self.detector.test_webhook()

    def save_detection_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.detector.save_detector_features(payload or {})

    def open_external_url(self, url: str) -> dict[str, Any]:
        target = (url or "").strip()
        if not (target.startswith("http://") or target.startswith("https://")):
            return {"ok": False, "error": "Invalid URL"}
        try:
            webbrowser.open(target)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def capture_chat(self, username: str) -> dict[str, Any]:
        """Capture the chat region of a Roblox window for a given account.
        Returns base64-encoded PNG without bringing window to foreground."""
        from core.screen_reader import ScreenReader
        from core.roblox_window import RobloxWindow

        acc = None
        for a in self.detector.accounts:
            if a.username == username:
                acc = a
                break
        if not acc or not acc.window_hwnd:
            return {"ok": False, "error": "No window assigned to this account"}

        hwnd = acc.window_hwnd
        if not ctypes.windll.user32.IsWindow(hwnd):
            return {"ok": False, "error": "Window no longer exists"}

        # Get client size to determine resolution profile
        cw, ch = RobloxWindow.get_client_size(hwnd)
        reader = ScreenReader()

        # Chat region: top-left area of the Roblox client
        # Approximate chat bounds (left ~2%, top ~3%, width ~25%, height ~45% of client)
        chat_x = max(0, int(cw * 0.02))
        chat_y = max(0, int(ch * 0.03))
        chat_w = max(100, int(cw * 0.25))
        chat_h = max(100, int(ch * 0.45))

        b64 = reader.capture_window_region_b64(hwnd, chat_x, chat_y, chat_w, chat_h)
        if not b64:
            return {"ok": False, "error": "Failed to capture window region"}

        return {"ok": True, "image": b64, "width": chat_w, "height": chat_h}


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    detector = BiomeDetector(ROOT_DIR)
    api = VaxiSolsApi(detector)

    title = "VaxiSols"
    webview.create_window(
        title=title,
        url=UI_FILE.as_uri(),
        js_api=api,
        width=800,
        height=600,
        frameless=True,
        easy_drag=True,
        shadow=True,
        resizable=True,
    )
    try:
        webview.start(debug=False, icon=str(WINDOW_ICON))
    finally:
        detector.stop()


if __name__ == "__main__":
    main()
