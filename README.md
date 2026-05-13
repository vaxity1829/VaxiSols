--------------------------------------------------
<img width="277" height="52" alt="image" src="https://github.com/user-attachments/assets/97a3fde5-47e4-4a73-bc32-99318995b856" />

--------------------------------------------------

Desktop companion for **Sol's RNG** on Windows: multi-account **log-based** detection (biomes, merchants, equipped auras) with optional Discord webhooks, plus a dark Material-style UI built with Python and pywebview.

**Disclaimer:** This is an unofficial automation assistant. Use only where allowed by Roblox and the game’s rules; authors are not responsible for bans or account issues.

Read https://vaxity1829.github.io/VaxiSols-website/

---

## Features

- **Detection service:** Tail Roblox client logs per linked account for biome changes, merchant arrivals (named log lines + optional banner/OCR assists), and aura equips.
- **Discord:** Multiple webhook URLs, embed formatting, optional private-server link field for messages.
- **Multi-account:** Add Roblox usernames and bind each to a specific Roblox window from the UI.
- **Settings:** Toggle biome / merchant / aura detection; optional merchant OCR (RapidOCR / Tesseract) and banner-color fallback (see in-app help).
- **Macro core (library):** Fishing loop, auto-sell, anchors from resolution profiles, plugins hook (`plugins/`), session reporting — exposed through `core/` / `features/` for scripting or future UI wiring.

Biome names from **Bloxstrap / Fishstrap** Rich Presence (`[BloxstrapRPC]` in logs) work best; vanilla Roblox logging may be sparser.

---

## Requirements

- **Windows 10/11** (primary target).
- **Python 3.11+** (for running from source).
- **Roblox** with logging available under `%LOCALAPPDATA%\Roblox\logs`.
- **Optional:** [Tesseract](https://github.com/tesseract-ocr/tesseract) on `PATH` if you enable OCR assist.
- **Optional:** Clone reference macros under `reference/` with `scripts\clone_references.ps1` for extra biome alias data (`reference/multiscope/assets/biomes.json`). The app still runs with built-in fallbacks if that file is missing.

---

## Quick start (from source)

```powershell
cd VaxiSols
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config\default.json.example config\default.json
python app.py
```

Or use `.\run.ps1` after the venv exists.

Edit `config\default.json` (see example) for webhook URLs and optional `active_resolution_profile` when using anchor-based features. **Do not commit real webhook URLs or private server links** — `config/default.json` is listed in `.gitignore`.

---

## Building the portable `.exe`

```powershell
.\build.ps1
```

Output: `dist\VaxiSols.exe` (one-file, windowed). Config and saves are written next to the executable under `config\default.json`.

Merchant OCR pulls **ONNX** models via `rapidocr-onnxruntime`; the bundle is large but self-contained.


## Project layout

| Path | Role |
|------|------|
| `app.py` | pywebview app, JS bridge API |
| `core/` | Biome detector, Roblox logs/windows, screen helpers, orchestrator |
| `features/` | Fishing, sell, merchant, anti-AFK, etc. |
| `integrations/` | Webhooks |
| `ui/` | Static HTML/CSS/JS UI |
| `config/` | `default.json.example`, `resolution_profiles.json` |
| `plugins/` | Optional `on_event` plugins |
| `website/` | Static macro guide site (optional hosting) |

---

## References & credits

Design influences (no wholesale code copies) include community macros such as FishSol-style fishing loops, Noteab-style log ideas, and MultiScope-style webhook/log naming.

