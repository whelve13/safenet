const DEFAULT_SETTINGS = {
  enabled: true,
  apiBaseUrl: "http://127.0.0.1:8000",
  severityThreshold: "medium",
  clickToReveal: true,
  maxSnippetLength: 280
};

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...stored };
}

async function saveSettings(partialSettings) {
  const merged = { ...(await getSettings()), ...partialSettings };
  await chrome.storage.sync.set(merged);
  return merged;
}

async function checkApiHealth(apiBaseUrl) {
  const response = await fetch(`${apiBaseUrl}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

async function analyzeText({ text, pageUrl, source = "extension" }) {
  const settings = await getSettings();
  const boundedText = text.trim().slice(0, settings.maxSnippetLength);
  if (!boundedText) {
    return null;
  }

  const response = await fetch(`${settings.apiBaseUrl}/v1/analyze/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: boundedText,
      source,
      page_url: pageUrl || null,
      persist_event_on_action: true
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Analyze failed (${response.status}): ${errorText}`);
  }

  return response.json();
}

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.sync.set(DEFAULT_SETTINGS);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      if (message.type === "getSettings") {
        sendResponse({ ok: true, settings: await getSettings() });
        return;
      }

      if (message.type === "saveSettings") {
        sendResponse({ ok: true, settings: await saveSettings(message.settings || {}) });
        return;
      }

      if (message.type === "checkApiHealth") {
        const settings = await getSettings();
        sendResponse({ ok: true, health: await checkApiHealth(settings.apiBaseUrl) });
        return;
      }

      if (message.type === "analyzeText") {
        const result = await analyzeText({
          text: message.text || "",
          pageUrl: message.pageUrl || sender?.tab?.url || null,
          source: message.source || "extension"
        });
        sendResponse({ ok: true, result });
        return;
      }

      sendResponse({ ok: false, error: "Unsupported message type." });
    } catch (error) {
      sendResponse({ ok: false, error: String(error.message || error) });
    }
  })();

  return true;
});

