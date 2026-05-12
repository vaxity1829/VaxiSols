const el = (id) => document.getElementById(id);
const on = (node, event, fn) => {
  if (node) node.addEventListener(event, fn);
};

const RARE_BIOMES = ["glitched","dreamspace","cyberspace","null","corruption","hell","heaven"];

const controls = {
  detectorBtn: el("detectorBtn"),
  detectorIcon: el("detectorIcon"),
  detectorStatus: el("detectorStatus"),
  newAccountInput: el("newAccountInput"),
  addAccountBtn: el("addAccountBtn"),
  windowPickerBtn: el("windowPickerBtn"),
  accountsList: el("accountsList"),
  webhookUrls: el("webhookUrls"),
  saveWebhookBtn: el("saveWebhookBtn"),
  testWebhookBtn: el("testWebhookBtn"),
  webhookTestResult: el("webhookTestResult"),
  privateServerInput: el("privateServerInput"),
  editPrivateServerBtn: el("editPrivateServerBtn"),
  eventLog: el("eventLog"),
  setBiome: el("setBiome"),
  setMerchant: el("setMerchant"),
  setAura: el("setAura"),
  setMerchantOcr: el("setMerchantOcr"),
  setMerchantVisual: el("setMerchantVisual"),
  saveSettingsBtn: el("saveSettingsBtn"),
  settingsSaveNote: el("settingsSaveNote"),
  themeToggle: el("themeToggle"),
  themeIcon: el("themeIcon"),
  btnClose: el("btnClose"),
  btnMinimize: el("btnMinimize"),
  btnMaximize: el("btnMaximize"),
};

let detectorState = "stopped";
let cachedWindows = [];

function applyTheme(theme) {
  const t = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", t);
  if (controls.themeIcon) controls.themeIcon.textContent = t === "dark" ? "dark_mode" : "light_mode";
  try { localStorage.setItem("vaxisols-theme", t); } catch (_) {}
}

function updateDetectorUI(state) {
  detectorState = state;
  const btn = controls.detectorBtn;
  const icon = controls.detectorIcon;
  const status = controls.detectorStatus;
  if (!btn || !icon || !status) return;
  btn.classList.remove("MuiFab-stopped", "MuiFab-running");
  if (state === "running") {
    btn.classList.add("MuiFab-running");
    icon.textContent = "stop";
    status.textContent = "running";
    btn.title = "Stop detector";
  } else {
    btn.classList.add("MuiFab-stopped");
    icon.textContent = "play_arrow";
    status.textContent = "stopped";
    btn.title = "Start detector";
  }
}

function isSettingsSectionActive() {
  const sec = el("settings-section");
  return !!(sec && sec.classList.contains("active"));
}

function showSection(name) {
  document.querySelectorAll(".content-section").forEach((s) => s.classList.remove("active"));
  document.querySelectorAll(".MuiDrawer-paper .MuiList-root .MuiListItem-root").forEach((s) => s.classList.remove("Mui-selected"));
  const sec = el(`${name}-section`);
  if (sec) sec.classList.add("active");
  const nav = document.querySelector(`[data-section="${name}"]`);
  if (nav) nav.classList.add("Mui-selected");
  if (name === "settings") {
    refreshState({ forceSettingsSync: true }).catch(() => {});
  }
}

function renderAccounts(accounts) {
  if (!controls.accountsList) return;
  if (!accounts || accounts.length === 0) {
    controls.accountsList.innerHTML = '<p style="color:var(--mui-text-disabled);text-align:center;padding:20px">No accounts yet. Add a Roblox username above, assign each window, then start.</p>';
    return;
  }
  controls.accountsList.innerHTML = accounts.map((a) => {
    const biomeDisplay = a.last_biome
      ? `<span class="AccountCard-biomeNormal">${a.last_biome}</span>`
      : '<span style="color:var(--mui-text-disabled)">Waiting...</span>';
    const windowLabel = a.window_title ? a.window_title : (a.window_hwnd ? `HWND ${a.window_hwnd}` : "No window assigned");

    // Build window selector options
    let windowOptions = `<option value="0">Select window...</option>`;
    for (const w of cachedWindows) {
      const selected = w.hwnd === a.window_hwnd ? " selected" : "";
      windowOptions += `<option value="${w.hwnd}"${selected}>${w.title || 'Roblox (PID ' + w.pid + ')'}</option>`;
    }
    if (a.window_hwnd && !cachedWindows.some(w => w.hwnd === a.window_hwnd)) {
      windowOptions += `<option value="${a.window_hwnd}" selected>${a.window_title || 'HWND ' + a.window_hwnd}</option>`;
    }

    return `
      <div class="AccountCard">
        <div class="AccountCard-info">
          <span class="material-icons AccountCard-icon">person</span>
          <div class="AccountCard-details">
            <div class="AccountCard-username">${a.username}</div>
            <div class="AccountCard-biome">Last biome: ${biomeDisplay} · ${a.biomes_detected || 0} biome changes</div>
            <div class="AccountCard-window">Window: ${windowLabel}</div>
          </div>
        </div>
        <div class="AccountCard-actions">
          <select class="AccountCard-windowSelect" onchange="setAccountWindow('${a.username}', parseInt(this.value))">${windowOptions}</select>
          <button class="AccountCard-deleteBtn" onclick="removeAccount('${a.username}')">
            <span class="material-icons" style="font-size:16px">delete</span>
          </button>
          <button class="AccountCard-deleteBtn" onclick="pickAndSetWindow('${a.username}')" title="Pick window by clicking">
            <span class="material-icons" style="font-size:16px">create</span>
          </button>
          <button class="AccountCard-deleteBtn" onclick="captureChat('${a.username}')" title="Capture chat">
            <span class="material-icons" style="font-size:16px">photo_camera</span>
          </button>
        </div>
      </div>`;
  }).join("");
}

async function setAccountWindow(username, hwnd) {
  if (!window.pywebview?.api) return;
  await window.pywebview.api.set_account_window(username, hwnd);
  await refreshState();
}

async function pickAndSetWindow(username) {
  if (!window.pywebview?.api) return;
  const result = await window.pywebview.api.pick_window();
  if (result?.ok) {
    await window.pywebview.api.set_account_window(username, result.hwnd);
    await refreshState();
  } else {
    alert(result?.error || "Failed to pick window");
  }
}

async function removeAccount(username) {
  if (!window.pywebview?.api) return;
  await window.pywebview.api.remove_account(username);
  await refreshState();
}

async function captureChat(username) {
  if (!window.pywebview?.api) return;
  const result = await window.pywebview.api.capture_chat(username);
  if (!result?.ok) {
    alert(result?.error || "Failed to capture chat");
    return;
  }
  // Show screenshot in a modal overlay
  let overlay = document.getElementById("chatCaptureOverlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "chatCaptureOverlay";
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:pointer";
    overlay.onclick = () => { overlay.style.display = "none"; };
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `<div style="position:relative;max-width:90%;max-height:90%">
    <div style="color:#fff;font-size:14px;margin-bottom:8px;text-align:center">${username} — Chat Capture</div>
    <img src="data:image/png;base64,${result.image}" style="max-width:100%;max-height:80vh;border-radius:8px;border:2px solid rgba(255,255,255,0.2)">
    <div style="color:rgba(255,255,255,0.5);font-size:11px;margin-top:6px;text-align:center">Click anywhere to close</div>
  </div>`;
  overlay.style.display = "flex";
}

async function refreshState(opts = {}) {
  if (!window.pywebview?.api) return;

  const forceSettingsSync = !!opts.forceSettingsSync;
  
  // Don't overwrite input fields that the user is actively editing
  const webhookFocused = document.activeElement === controls.webhookUrls;
  const privateServerFocused = document.activeElement === controls.privateServerInput;
  
  const [state, windows] = await Promise.all([
    window.pywebview.api.get_state(),
    window.pywebview.api.get_roblox_windows(),
  ]);
  cachedWindows = windows || [];
  const backendState = (state.state || "stopped").toLowerCase();
  updateDetectorUI(backendState === "running" ? "running" : "stopped");
  renderAccounts(state.accounts);
  
  // Only update input fields if user is NOT actively typing in them
  if (controls.webhookUrls && !webhookFocused) {
    controls.webhookUrls.value = (state.webhook_urls || []).join("\n");
  }
  if (controls.privateServerInput && !privateServerFocused) {
    controls.privateServerInput.value = state.private_server || "";
  }

  // Polling refreshState runs every 1s — never stomp Settings toggles while that tab is open (unless forcing sync).
  const syncDetectorFeatures = forceSettingsSync || !isSettingsSectionActive();
  const df = state.detector_features;
  if (syncDetectorFeatures && df && controls.setBiome) {
    controls.setBiome.checked = df.biome !== false;
    controls.setMerchant.checked = df.merchant !== false;
    controls.setAura.checked = df.aura !== false;
    controls.setMerchantOcr.checked = !!df.merchant_use_ocr;
    controls.setMerchantVisual.checked = df.merchant_visual_fallback !== false;
  }
  
  if (controls.eventLog) {
    const lines = (state.recent_events || [])
      .map((e) => `[${new Date((e.timestamp || 0) * 1000).toLocaleTimeString()}] ${e.type}${e.username ? " (" + e.username + ")" : ""}: ${e.message}`)
      .join("\n");
    controls.eventLog.textContent = lines || "No events yet.";
  }
}

// Start/stop detector
on(controls.detectorBtn, "click", async () => {
  if (!window.pywebview?.api) return;
  if (detectorState === "running") await window.pywebview.api.stop_detector();
  else await window.pywebview.api.start_detector();
  await refreshState();
});

on(controls.saveSettingsBtn, "click", async () => {
  if (!window.pywebview?.api?.save_detection_settings) return;
  if (controls.settingsSaveNote) controls.settingsSaveNote.textContent = "";
  const payload = {
    biome: !!(controls.setBiome && controls.setBiome.checked),
    merchant: !!(controls.setMerchant && controls.setMerchant.checked),
    aura: !!(controls.setAura && controls.setAura.checked),
    merchant_use_ocr: !!(controls.setMerchantOcr && controls.setMerchantOcr.checked),
    merchant_visual_fallback: !!(controls.setMerchantVisual && controls.setMerchantVisual.checked),
  };
  const result = await window.pywebview.api.save_detection_settings(payload);
  if (controls.settingsSaveNote) {
    controls.settingsSaveNote.textContent = result?.ok ? "Saved." : `Could not save: ${result?.error || "unknown"}`;
  }
  await refreshState({ forceSettingsSync: true });
});

// Theme
on(controls.themeToggle, "click", () => {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  applyTheme(current === "dark" ? "light" : "dark");
});

// Sidebar nav
document.querySelectorAll(".MuiDrawer-paper .MuiList-root .MuiListItem-root").forEach((item) => {
  on(item, "click", (e) => {
    e.preventDefault();
    const section = item.getAttribute("data-section");
    if (section) showSection(section);
  });
});

// External links (open in system browser through backend API)
document.querySelectorAll("[data-open-url]").forEach((node) => {
  on(node, "click", async (e) => {
    e.preventDefault();
    const url = node.getAttribute("data-open-url");
    if (!url) return;
    if (window.pywebview?.api?.open_external_url) {
      await window.pywebview.api.open_external_url(url);
      return;
    }
    window.open(url, "_blank");
  });
});

// Add account
on(controls.addAccountBtn, "click", async () => {
  if (!window.pywebview?.api) return;
  const input = controls.newAccountInput;
  if (!input) return;
  const username = input.value.trim();
  if (!username) return;
  const result = await window.pywebview.api.add_account(username);
  if (result?.ok) {
    input.value = "";
    await refreshState();
  } else {
    alert(result?.error || "Failed to add account");
  }
});

// Window picker (global)
on(controls.windowPickerBtn, "click", async () => {
  if (!window.pywebview?.api) return;
  const result = await window.pywebview.api.pick_window();
  if (result?.ok) {
    // If there's only one account, auto-assign
    const state = await window.pywebview.api.get_state();
    if (state.accounts && state.accounts.length === 1) {
      await window.pywebview.api.set_account_window(state.accounts[0].username, result.hwnd);
      await refreshState();
    } else {
      alert(`Selected window: ${result.title}\n\nUse the picker button on an account to assign this window.`);
    }
  } else {
    alert(result?.error || "Failed to pick window");
  }
});

// Enter key to add account
on(controls.newAccountInput, "keydown", async (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    if (controls.addAccountBtn) controls.addAccountBtn.click();
  }
});

// Save webhooks
on(controls.saveWebhookBtn, "click", async () => {
  if (!window.pywebview?.api) return;
  const urls = (controls.webhookUrls?.value || "").split("\n").map((x) => x.trim()).filter(Boolean);
  const privateServer = controls.privateServerInput?.value?.trim() || "";
  await window.pywebview.api.save_webhooks(urls, privateServer);
  await refreshState();
});

// Edit private server
on(controls.editPrivateServerBtn, "click", async () => {
  if (!window.pywebview?.api) return;
  const currentPrivateServer = controls.privateServerInput?.value?.trim() || "";
  const newPrivateServer = prompt("Edit Private Server URL:", currentPrivateServer);
  if (newPrivateServer !== null) {
    controls.privateServerInput.value = newPrivateServer;
    await window.pywebview.api.save_webhooks(
      (controls.webhookUrls?.value || "").split("\n").map((x) => x.trim()).filter(Boolean),
      newPrivateServer
    );
  }
  // Don't save if user cancelled (null) to prevent clearing input
});

// Test webhook
on(controls.testWebhookBtn, "click", async () => {
  if (!window.pywebview?.api) return;
  if (controls.webhookTestResult) controls.webhookTestResult.textContent = "Sending test...";
  const urls = (controls.webhookUrls?.value || "").split("\n").map((x) => x.trim()).filter(Boolean);
  const privateServer = controls.privateServerInput?.value?.trim() || "";
  await window.pywebview.api.save_webhooks(urls, privateServer);
  const result = await window.pywebview.api.test_webhook();
  if (!controls.webhookTestResult) return;
  if (result?.ok) {
    controls.webhookTestResult.textContent = "✓ Test successful";
    controls.webhookTestResult.style.color = "var(--mui-primary)";
  } else {
    controls.webhookTestResult.textContent = `✗ Failed: ${result?.error || "Unknown"}`;
    controls.webhookTestResult.style.color = "#ff5252";
  }
});

// macOS title bar buttons (pywebview window control)
on(controls.btnClose, "click", async () => {
  if (window.pywebview?.api) await window.pywebview.api.close_window();
});
on(controls.btnMinimize, "click", async () => {
  if (window.pywebview?.api) {
    await window.pywebview.api.minimize_window();
  }
});

// Handle cursor state for window dragging
function handleCursorState() {
  const checkCursor = (element) => {
    // Skip cursor detection for textareas and inputs to allow resizing
    if (element && (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT' || element.closest('textarea') || element.closest('input'))) {
      return;
    }
    
    const cursor = window.getComputedStyle(element || document.body).cursor;
    const isNormalCursor = cursor === 'auto' || cursor === 'default';
    
    // Disable dragging on panels when cursor is NOT normal
    const panels = document.querySelectorAll('.MuiCard-root, .MuiCardContent-root, .MuiList-root, .content-section');
    panels.forEach(panel => {
      if (!isNormalCursor) {
        panel.style.webkitAppRegion = 'no-drag';
      } else {
        panel.style.webkitAppRegion = '';
      }
    });
  };
  
  // Check cursor state on mouse movement over different elements
  document.addEventListener('mousemove', (e) => {
    checkCursor(e.target);
  });
  
  // Also check periodically as fallback
  setInterval(() => checkCursor(), 100);
}

// Prevent text highlighting
function preventTextSelection() {
  document.addEventListener('selectstart', (e) => {
    // Allow selection in input fields and textareas
    if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      e.preventDefault();
    }
  });
  
  // Also prevent drag selection
  document.addEventListener('dragstart', (e) => {
    if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      e.preventDefault();
    }
  });
}

// Init
window.addEventListener("pywebviewready", async () => {
  try {
    applyTheme(localStorage.getItem("vaxisols-theme") || "dark");
  } catch (_) {
    applyTheme("dark");
  }
  if (!window.pywebview?.api) return;
  const cfg = await window.pywebview.api.load_config();
  if (controls.webhookUrls) controls.webhookUrls.value = (cfg.webhooks?.urls || []).join("\n");
  await refreshState();
  
  // Initialize cursor state handler
  handleCursorState();
  
  // Initialize text selection prevention
  preventTextSelection();
  
  // Hide loading screen and show app
  setTimeout(() => {
    const loadingScreen = document.getElementById('loading-screen');
    const appLayout = document.querySelector('.app-layout');
    if (loadingScreen) {
      loadingScreen.style.opacity = '0';
      loadingScreen.style.transition = 'opacity 0.3s ease-out';
      setTimeout(() => {
        loadingScreen.style.display = 'none';
        if (appLayout) {
          appLayout.style.display = 'flex';
          appLayout.style.opacity = '0';
          appLayout.style.transition = 'opacity 0.3s ease-in';
          setTimeout(() => {
            appLayout.style.opacity = '1';
          }, 50);
        }
      }, 300);
    } else {
      // Fallback if loading screen not found
      if (appLayout) appLayout.style.display = 'flex';
    }
  }, 1000); // Show loading screen for at least 1 second
});

// Also hide loading screen if pywebviewready doesn't fire (fallback)
setTimeout(() => {
  const loadingScreen = document.getElementById('loading-screen');
  const appLayout = document.querySelector('.app-layout');
  if (loadingScreen && loadingScreen.style.display !== 'none') {
    loadingScreen.style.opacity = '0';
    loadingScreen.style.transition = 'opacity 0.3s ease-out';
    setTimeout(() => {
      loadingScreen.style.display = 'none';
      if (appLayout) {
        appLayout.style.display = 'flex';
        appLayout.style.opacity = '0';
        appLayout.style.transition = 'opacity 0.3s ease-in';
        setTimeout(() => {
          appLayout.style.opacity = '1';
        }, 50);
      }
    }, 300);
  }
}, 2000); // Fallback after 2 seconds

setInterval(() => { refreshState().catch(() => {}); }, 1000);
