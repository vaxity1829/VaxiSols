# VaxiSols Macro Development Plan

## Goal
Combine the **features** of three Sol's RNG macros into one Python desktop app:
- **FishSol-Macro** (AutoHotkey) → fishing + auto-sell + pathing + failsafes
- **Noteab-Macro** (Coteab fork) → biome/aura detection via logs + merchant OCR + potions + webhooks
- **MultiScope** → multi-account + anti-AFK stealth + hidden mode + performance engine

## Current State
The skeleton exists but all feature services are **stubs** (random events, no real screen interaction):
- `features/fishing.py` — fake cast counter, no mouse/keyboard input
- `features/biome_aura.py` — random biome names, no log reading
- `features/merchant.py` — random encounters, no OCR
- `features/anti_afk.py` — placeholder, no actual input
- `core/orchestrator.py` — working loop/state machine ✓
- `core/hotkeys.py` — working F1/F2/F3 ✓
- `core/calibration.py` — resolution profiles loaded ✓
- `integrations/webhooks.py` — working Discord POST ✓
- `ui/` — working MUI-themed interface ✓

---

## Phase 1: Screen Interaction Foundation
**Purpose:** Build the low-level primitives all features depend on.

### 1.1 Roblox Window Manager (`core/roblox_window.py`)
- Find Roblox window by class name (`WINDOWSCLIENT` for UWP, or title)
- Bring to foreground / send to background (hidden mode from MultiScope)
- Get window rect, client area offset
- Screenshot capture of specific regions (using `mss` or `Pillow` + `win32gui`)

### 1.2 Input Controller (`core/input_controller.py`)
- `click(x, y)` — screen-coordinate click with randomized offset
- `hold_key(key, duration)` — key press/release
- `send_key(key)` — single key tap
- `scroll(direction, clicks)` — mouse scroll
- All inputs with small random delays to appear human-like
- Use `pyautogui` (already in requirements) + `ctypes` for SendInput fallback

### 1.3 Screen Reader / OCR (`core/screen_reader.py`)
- Pixel color sampling at coordinates (for fishing bobber detection)
- Region screenshot for OCR (merchant items, biome text)
- Template matching with `Pillow` / `opencv-python` (image recognition)
- Roblox log file reader (`%LOCALAPPDATA%\Roblox\logs\` latest .log)

---

## Phase 2: Fishing + Auto-Sell (from FishSol-Macro)
**Purpose:** Real fishing cast detection and auto-sell pathing.

### 2.1 Fishing Service Rewrite (`features/fishing.py`)
- **Cast detection**: Click fishing button, wait for bobber pixel change
- **Reel detection**: Monitor bobber area for "!" indicator pixel/color shift
- **Auto-reel**: Click when fish bites
- **Failsafe**: If no bite within `fishingFailsafeTime` (31s default), recast
- **Advanced fishing detection**: Monitor for catch text in UI area
- Resolution-aware coordinates from `calibration.py` profiles

### 2.2 Auto-Sell Pathing (`features/auto_sell.py`) — NEW
- Walk to Captain Flarg NPC (key sequence pathing)
- Click sell menu → sell all
- Walk back to fishing spot
- Multiple pathing modes: VIP pathing, standard pathing
- AZERTY/QWERTY keyboard layout support
- Pathing failsafe: if stuck > 61s, abort and rejoin

### 2.3 Auto-Rejoin Failsafe (`features/auto_rejoin.py`) — NEW
- Detect if kicked/disconnected (Roblox window title change or log entry)
- Rejoin via private server link
- Configurable timeout (320s default from FishSol)

---

## Phase 3: Biome & Aura Detection (from Noteab-Macro)
**Purpose:** Real-time biome/aura reading from Roblox logs.

### 3.1 BiomeAura Service Rewrite (`features/biome_aura.py`)
- **Log file monitoring**: Tail Roblox's latest log file for biome change lines
- **Biome detection**: Parse log entries like `"entered biome: X"` — 99.99% accurate
- **Aura detection**: Parse log entries for rare aura rolls
- **Supported biomes**: Windy, Snowy, Rainy, Heaven, Hell, Starfall, Corruption, Sand Storm, Null, Glitched, Dreamspace, Cyberspace (always-on for rare ones)
- **Biome-specific webhooks**: Filter which biomes trigger notifications
- **Private server link**: Auto-rejoin to specific server on rare biome

### 3.2 Auto Potion Popper (`features/auto_potion.py`) — NEW
- Detect when inside specific biomes (Glitched, Dreamspace, Cyberspace)
- Auto-pop potions when entering these biomes
- Configurable potion types

---

## Phase 4: Merchant Detection (from Noteab-Macro)
**Purpose:** OCR-based merchant spotting and auto-purchase.

### 4.1 Merchant Service Rewrite (`features/merchant.py`)
- **Merchant detection**: Screen region monitoring for merchant NPC appearance
- **OCR reading**: Use `pytesseract` or `easyocr` to read merchant item names
- **Auto-purchase**: Click buy button for configured items
- **Merchant webhooks**: Send notification when merchant appears with item list
- **Purchase webhooks**: Confirm what was purchased

---

## Phase 5: Anti-AFK + Stealth (from MultiScope)
**Purpose:** Prevent AFK kicks and allow background operation.

### 5.1 AntiAfk Service Rewrite (`features/anti_afk.py`)
- **Periodic input**: Send small mouse movements or key presses every ~20s
- **Hidden mode**: Move Roblox window off-screen or minimize while keeping it active
- **Stealth**: Inputs that don't interfere with other macro features running
- **Randomized intervals**: Vary timing to avoid detection patterns

---

## Phase 6: Multi-Account Support (from MultiScope)
**Purpose:** Run monitoring for multiple Roblox instances.

### 6.1 Multi-Instance Manager (`core/multi_instance.py`) — NEW
- Detect multiple running Roblox windows
- Assign each window to a tracked "account" slot
- Per-account biome/aura/merchant monitoring
- Per-account webhook routing (different URLs per account)
- Per-account anti-AFK

### 6.2 Orchestrator Update (`core/orchestrator.py`)
- Support N parallel account loops instead of single loop
- Per-account feature toggles
- Aggregated dashboard stats

---

## Phase 7: Extra Features (from FishSol plugins)
**Purpose:** Optional advanced features.

### 7.1 Auto-Crafter (`features/auto_crafter.py`) — NEW
- Detect crafter NPC appearance
- Auto-craft configured items
- Webhook on craft completion

### 7.2 Strange Controller (`features/strange_controller.py`) — NEW
- Periodically check for Strange Controller item
- Auto-use when detected
- Configurable interval (~21 min)

### 7.3 Biome Randomizer (`features/biome_randomizer.py`) — NEW
- Periodically use biome randomizer item
- Configurable interval (~21 min)

### 7.4 Auto-Unequip (`features/auto_unequip.py`) — NEW
- Remove equipped items before fishing to prevent interference
- Re-equip after session

### 7.5 Auto-Close Chat (`features/auto_close_chat.py`) — NEW
- Detect open chat overlay
- Press Enter/Escape to close it

---

## Phase 8: UI Updates for New Features
**Purpose:** Expose all new features in the MUI interface.

### 8.1 Dashboard Enhancements
- Per-feature stat cards (casts, biomes found, merchant encounters, etc.)
- Live session timer with format (HH:MM:SS)
- Running/paused indicator synced with FAB button

### 8.2 Features Panel Expansion
- Toggle for each new feature (auto-potion, auto-crafter, etc.)
- Per-feature configuration (intervals, thresholds)
- Biome filter checkboxes (which biomes trigger webhooks)

### 8.3 New Settings Section
- Resolution profile selector dropdown
- Keyboard layout toggle (QWERTY/AZERTY)
- Private server link input
- Failsafe timeout settings
- Hidden mode toggle

### 8.4 Enhanced Event Log
- Color-coded event types (biome=red, aura=gold, merchant=blue, etc.)
- Filter by event type
- Clear log button

---

## Implementation Priority Order
1. **Phase 1** (Screen foundation) — everything else depends on this
2. **Phase 3** (Biome/Aura via logs) — easiest real feature, highest impact
3. **Phase 5** (Anti-AFK) — simple, essential for AFK sessions
4. **Phase 2** (Fishing) — core gameplay loop, most complex
5. **Phase 4** (Merchant OCR) — requires OCR dependency
6. **Phase 8** (UI updates) — as features come online
7. **Phase 6** (Multi-account) — advanced, can wait
8. **Phase 7** (Extra features) — nice-to-haves

## New Dependencies Needed
```
mss              # Fast screen capture
opencv-python    # Template matching / image recognition
pytesseract      # OCR for merchant detection (requires Tesseract-OCR installed)
easyocr          # Alternative OCR (no external install needed, uses PyTorch)
win32gui         # Window management (pywin32)
```

## Key Technical Decisions
- **Biome detection method**: Log file reading (from Noteab) — more reliable than pixel scanning
- **Fishing detection method**: Pixel color monitoring at bobber coordinates (from FishSol)
- **Merchant detection method**: OCR of screen region (from Noteab)
- **Input method**: `pyautogui` + `ctypes.SendInput` for reliability
- **Multi-account**: Window handle enumeration via `win32gui`
