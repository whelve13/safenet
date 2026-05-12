const SCAN_SELECTOR = "p,li,blockquote,article,section,div,span,h1,h2,h3,h4,h5,h6";
const MAX_VISIBLE_NODES_PER_SCAN = 25;
const analyzedCache = new WeakMap();
const pendingNodes = new WeakSet();

let settings = null;
let mutationTimer = null;
const inputDebounce = new WeakMap();

function severityRank(severity) {
  return { low: 0, medium: 1, high: 2, critical: 3 }[severity] ?? 0;
}

function blurRadiusForSeverity(severity) {
  if (severity === "critical") return 8;
  if (severity === "high") return 5;
  if (severity === "medium") return 3;
  return 0;
}

function injectStyles() {
  if (document.getElementById("safenet-style")) return;
  const style = document.createElement("style");
  style.id = "safenet-style";
  style.textContent = `
    .safenet-flagged {
      transition: filter 0.2s ease;
      cursor: help;
    }
    .safenet-revealed {
      filter: none !important;
    }
    .safenet-input-flagged {
      transition: filter 0.2s ease, outline 0.2s ease;
      outline: 2px solid #ef4444 !important;
      outline-offset: 2px;
    }
  `;
  document.head.appendChild(style);
}

function getElementText(element) {
  const raw = (element.innerText || element.textContent || "").trim();
  return raw.replace(/\s+/g, " ");
}

function isVisible(element) {
  const rect = element.getBoundingClientRect();
  const style = window.getComputedStyle(element);
  return (
    rect.width > 0 &&
    rect.height > 0 &&
    style.visibility !== "hidden" &&
    style.display !== "none"
  );
}

function shouldSendForModeration(text) {
  return text.length >= 12 && text.length <= (settings?.maxSnippetLength || 280);
}

function applyTooltipAndClickToReveal(element, result) {
  const explanation = result?.explanation?.reason || "Flagged by SafeNet moderation.";
  element.title = `SafeNet: ${result.severity.toUpperCase()} (${result.decision}) - ${explanation}`;

  if (settings?.clickToReveal && !element.dataset.safenetRevealBound) {
    element.dataset.safenetRevealBound = "1";
    element.addEventListener("click", () => {
      element.classList.toggle("safenet-revealed");
    });
  }
}

function applyModerationToElement(element, result) {
  const radius = blurRadiusForSeverity(result.severity);
  element.classList.add("safenet-flagged");
  element.style.filter = radius > 0 ? `blur(${radius}px)` : "none";
  applyTooltipAndClickToReveal(element, result);
}

function clearModerationFromElement(element) {
  element.classList.remove("safenet-flagged", "safenet-revealed");
  element.style.filter = "";
  element.title = "";
}

function shouldApplyAction(result) {
  if (!result || result.decision === "allow") return false;
  const threshold = settings?.severityThreshold || "medium";
  return severityRank(result.severity) >= severityRank(threshold);
}

async function analyzeAndModerateNode(element) {
  const text = getElementText(element);
  if (!shouldSendForModeration(text)) return;

  const cached = analyzedCache.get(element);
  if (cached === text || pendingNodes.has(element)) return;

  pendingNodes.add(element);
  try {
    const response = await chrome.runtime.sendMessage({
      type: "analyzeText",
      source: "extension",
      text,
      pageUrl: window.location.href
    });

    if (!response?.ok || !response?.result) return;

    if (shouldApplyAction(response.result)) {
      applyModerationToElement(element, response.result);
    } else {
      clearModerationFromElement(element);
    }

    analyzedCache.set(element, text);
  } finally {
    pendingNodes.delete(element);
  }
}

async function scanVisibleText() {
  if (!settings?.enabled) return;

  const elements = Array.from(document.querySelectorAll(SCAN_SELECTOR))
    .filter((el) => !el.closest("script,style,noscript,textarea,input"))
    .filter(isVisible)
    .slice(0, MAX_VISIBLE_NODES_PER_SCAN);

  await Promise.all(elements.map((el) => analyzeAndModerateNode(el)));
}

function clearInputModeration(input) {
  input.classList.remove("safenet-input-flagged");
  input.style.filter = "";
  input.title = "";
}

function applyInputModeration(input, result) {
  const radius = blurRadiusForSeverity(result.severity);
  input.classList.add("safenet-input-flagged");
  input.style.filter = radius > 0 ? `blur(${radius}px)` : "";
  input.title = `SafeNet: ${result.severity.toUpperCase()} (${result.decision}) - ${result.explanation.reason}`;
}

async function analyzeUserInput(input) {
  if (!settings?.enabled) return;
  const text = (input.value || input.innerText || "").trim();
  if (!shouldSendForModeration(text)) {
    clearInputModeration(input);
    return;
  }

  const response = await chrome.runtime.sendMessage({
    type: "analyzeText",
    source: "extension",
    text,
    pageUrl: window.location.href
  });

  if (!response?.ok || !response?.result) return;
  if (shouldApplyAction(response.result)) {
    applyInputModeration(input, response.result);
  } else {
    clearInputModeration(input);
  }
}

function bindInputListeners() {
  document.addEventListener(
    "input",
    (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) return;

      if (inputDebounce.has(target)) {
        clearTimeout(inputDebounce.get(target));
      }

      const timer = setTimeout(() => {
        analyzeUserInput(target);
      }, 350);
      inputDebounce.set(target, timer);
    },
    true
  );
}

function initMutationObserver() {
  const observer = new MutationObserver(() => {
    if (!settings?.enabled) return;
    clearTimeout(mutationTimer);
    mutationTimer = setTimeout(() => {
      scanVisibleText();
    }, 450);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });
}

async function loadSettings() {
  const response = await chrome.runtime.sendMessage({ type: "getSettings" });
  if (response?.ok && response.settings) {
    settings = response.settings;
  }
}

async function start() {
  injectStyles();
  await loadSettings();
  bindInputListeners();
  initMutationObserver();
  await scanVisibleText();
  setInterval(scanVisibleText, 8000);
}

start();

