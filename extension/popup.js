const enabledToggle = document.getElementById("enabledToggle");
const apiBaseUrlInput = document.getElementById("apiBaseUrl");
const severityThresholdSelect = document.getElementById("severityThreshold");
const clickToRevealToggle = document.getElementById("clickToReveal");
const saveButton = document.getElementById("saveButton");
const healthButton = document.getElementById("healthButton");
const statusDiv = document.getElementById("status");

function setStatus(message) {
  statusDiv.textContent = `Status: ${message}`;
}

async function loadSettings() {
  const response = await chrome.runtime.sendMessage({ type: "getSettings" });
  if (!response?.ok) {
    setStatus("failed to load settings");
    return;
  }

  const settings = response.settings;
  enabledToggle.checked = !!settings.enabled;
  apiBaseUrlInput.value = settings.apiBaseUrl || "http://127.0.0.1:8000";
  severityThresholdSelect.value = settings.severityThreshold || "medium";
  clickToRevealToggle.checked = !!settings.clickToReveal;
  setStatus("ready");
}

async function saveSettings() {
  const settings = {
    enabled: enabledToggle.checked,
    apiBaseUrl: apiBaseUrlInput.value.trim(),
    severityThreshold: severityThresholdSelect.value,
    clickToReveal: clickToRevealToggle.checked
  };

  const response = await chrome.runtime.sendMessage({
    type: "saveSettings",
    settings
  });

  if (!response?.ok) {
    setStatus("save failed");
    return;
  }

  setStatus("settings saved");
}

async function checkHealth() {
  setStatus("checking API...");
  const response = await chrome.runtime.sendMessage({ type: "checkApiHealth" });
  if (!response?.ok) {
    setStatus(`API offline (${response?.error || "unknown error"})`);
    return;
  }
  setStatus("API online");
}

saveButton.addEventListener("click", saveSettings);
healthButton.addEventListener("click", checkHealth);

loadSettings();

