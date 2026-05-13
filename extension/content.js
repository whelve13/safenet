const MAX_TEXT_NODES_PER_SCAN = 160;
const MAX_SCAN_ROOTS = 120;
const ANALYZE_CONCURRENCY = 6;
const ANALYSIS_DEDUPE_WINDOW_MS = 30_000;
const MUTATION_DEBOUNCE_MS = 500;
const PERIODIC_SCAN_MS = 8_000;
const INLINE_BLUR_CLASS = "safenet-inline-blur";
const WHOLE_BLUR_CLASS = "safenet-flagged";
const REVEALED_CLASS = "safenet-revealed";
const SKIP_ANCESTOR_SELECTOR = [
  "script",
  "style",
  "noscript",
  "textarea",
  "input",
  "select",
  "option",
  "button",
  ".safenet-input-flagged",
  ".safenet-inline-blur",
  "[data-safenet-skip='1']"
].join(",");
const SKIP_PARENT_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "INPUT", "BODY", "MAIN", "HTML"]);
const BLUR_TARGET_TAGS = new Set([
  "A",
  "P",
  "LI",
  "SPAN",
  "DIV",
  "H1",
  "H2",
  "H3",
  "H4",
  "H5",
  "H6",
  "ARTICLE",
  "SECTION",
  "BLOCKQUOTE"
]);
const SCAN_ROOT_SELECTOR = [
  "article",
  "section",
  "aside",
  "div",
  "p",
  "li",
  "a",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "blockquote",
  "[role='article']",
  "[role='link']",
  "[role='heading']",
  "[role='listitem']"
].join(",");

let settings = null;
let mutationTimer = null;
let isApplyingDomMutation = false;
const inputDebounce = new WeakMap();
const pendingNodeRequests = new WeakSet();
const analyzedNodeText = new WeakMap();
const inlineProcessedSignatures = new WeakMap();
const analysisCache = new Map();
const pendingTextSignatures = new Set();
const pendingMutationRoots = new Set();

function severityRank(severity) {
  return { low: 0, medium: 1, high: 2, critical: 3 }[severity] ?? 0;
}

function blurRadiusForSeverity(severity) {
  if (severity === "critical") return 8;
  if (severity === "high") return 5;
  if (severity === "medium") return 3;
  return 0;
}

function normalizeWhitespace(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function normalizeForSignature(text) {
  return normalizeWhitespace(text).toLowerCase();
}

function cleanupAnalysisCache() {
  const now = Date.now();
  for (const [key, value] of analysisCache.entries()) {
    if (now - value.timestamp > ANALYSIS_DEDUPE_WINDOW_MS) {
      analysisCache.delete(key);
    }
  }
}

function isElementVisible(element) {
  if (!element || !element.isConnected) return false;
  const style = window.getComputedStyle(element);
  if (style.visibility === "hidden" || style.display === "none" || style.opacity === "0") return false;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function shouldSendForModeration(text) {
  const maxSnippetLength = settings?.maxSnippetLength || 280;
  const normalizedLength = normalizeWhitespace(text).length;
  return normalizedLength >= 3 && normalizedLength <= maxSnippetLength;
}

function escapeRegExp(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function phraseToRegex(phrase) {
  const tokens = normalizeWhitespace(phrase).split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return null;

  const tokenPatterns = tokens.map((token) => `\\b${escapeRegExp(token)}\\b`);
  const pattern = tokenPatterns.join("(?:[\\W_]+)");
  return new RegExp(pattern, "giu");
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
    .safenet-inline-blur {
      filter: blur(3px);
      cursor: help;
      transition: filter 0.2s ease;
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

function buildWholeMessageTooltip(result) {
  const explanation = result?.explanation || {};
  const score = typeof result?.toxicity_score === "number" ? result.toxicity_score.toFixed(2) : "n/a";
  const method = result?.detection_method || "unknown";
  const decision = result?.decision || "allow";
  const severity = result?.severity || "low";
  const hfScore = typeof explanation.hf_score === "number" ? explanation.hf_score.toFixed(2) : "unavailable";
  const dictScore = typeof explanation.dict_score === "number" ? explanation.dict_score.toFixed(2) : "0.00";

  return [
    `SafeNet score: ${score}`,
    `Severity: ${severity}`,
    `Method: ${method}`,
    `Decision: ${decision}`,
    `Toxic-BERT: ${hfScore}`,
    `Dictionary: ${dictScore}`
  ].join("\n");
}

function bindRevealBehavior(element) {
  if (!settings?.clickToReveal) return;
  if (element.dataset.safenetRevealBound) return;
  element.dataset.safenetRevealBound = "1";
  element.addEventListener("click", () => {
    element.classList.toggle(REVEALED_CLASS);
  });
}

function applyWholeMessageBlur(element, result, sourceSignature) {
  if (!element) return;
  const radius = blurRadiusForSeverity(result.severity);
  element.classList.add(WHOLE_BLUR_CLASS);
  element.style.filter = radius > 0 ? `blur(${radius}px)` : "none";
  element.title = buildWholeMessageTooltip(result);
  element.dataset.safenetSourceSignature = sourceSignature || "";
  bindRevealBehavior(element);
}

function clearWholeMessageBlur(element, sourceSignature) {
  if (!element) return;
  if (sourceSignature && element.dataset.safenetSourceSignature !== sourceSignature) return;
  element.classList.remove(WHOLE_BLUR_CLASS, REVEALED_CLASS);
  element.style.filter = "";
  element.title = "";
  delete element.dataset.safenetSourceSignature;
  if (element.dataset.safenetRevealBound) {
    delete element.dataset.safenetRevealBound;
  }
}

function shouldApplyWholeMessageAction(result) {
  if (!result || result.decision === "allow") return false;
  const threshold = settings?.severityThreshold || "medium";
  return severityRank(result.severity) >= severityRank(threshold);
}

function getBlurTargetFromTextNode(textNode) {
  let element = textNode?.parentElement || null;
  while (element && element !== document.body && element !== document.documentElement) {
    if (BLUR_TARGET_TAGS.has(element.tagName)) return element;
    if (SKIP_PARENT_TAGS.has(element.tagName)) return null;
    element = element.parentElement;
  }
  return null;
}

function appendFallbackMatches(rawText, result, matches) {
  const explanation = result?.explanation || {};
  const phraseCandidates = Array.isArray(explanation.matched_phrases) ? explanation.matched_phrases : [];
  const termCandidates = Array.isArray(explanation.matched_terms) ? explanation.matched_terms : [];
  const candidates = [
    ...phraseCandidates.map((phrase) => ({ text: phrase, type: "phrase" })),
    ...termCandidates.map((term) => ({ text: term, type: "term" }))
  ];

  for (const candidate of candidates) {
    const regex = phraseToRegex(candidate.text);
    if (!regex) continue;

    let match;
    while ((match = regex.exec(rawText)) !== null) {
      const start = match.index;
      const end = start + match[0].length;
      if (end > start) {
        matches.push({
          start,
          end,
          type: candidate.type,
          value: normalizeWhitespace(candidate.text)
        });
      }
      if (regex.lastIndex === match.index) {
        regex.lastIndex += 1;
      }
    }
  }
}

function extractDictionaryMatches(rawText, result) {
  const explanation = result?.explanation || {};
  const matches = [];
  const pushSpan = (span, typeKey, valueKey) => {
    if (!span || typeof span.start !== "number" || typeof span.end !== "number") return;
    const start = Math.max(0, span.start);
    const end = Math.min(rawText.length, span.end);
    if (end <= start) return;
    matches.push({
      start,
      end,
      type: typeKey,
      value: normalizeWhitespace(span[valueKey] || rawText.slice(start, end))
    });
  };

  const phraseSpans = Array.isArray(explanation.matched_phrase_spans) ? explanation.matched_phrase_spans : [];
  const termSpans = Array.isArray(explanation.matched_term_spans) ? explanation.matched_term_spans : [];

  for (const span of phraseSpans) pushSpan(span, "phrase", "phrase");
  for (const span of termSpans) pushSpan(span, "term", "term");

  if (matches.length === 0) {
    appendFallbackMatches(rawText, result, matches);
  }

  matches.sort((a, b) => (a.start - b.start) || ((b.end - b.start) - (a.end - a.start)));
  const selected = [];
  let lastEnd = -1;
  for (const item of matches) {
    if (item.start < lastEnd) continue;
    selected.push(item);
    lastEnd = item.end;
  }
  return selected;
}

function applyInlinePhraseBlur(textNode, result) {
  if (!textNode || !textNode.parentElement) return false;
  if (!textNode.isConnected) return false;
  if (textNode.parentElement.closest(`.${INLINE_BLUR_CLASS}`)) return false;

  const rawText = textNode.nodeValue || "";
  if (!rawText.trim()) return false;

  const parent = textNode.parentElement;
  const nodeSignature = normalizeForSignature(rawText);
  const parentSignatures = inlineProcessedSignatures.get(parent) || new Set();
  if (parentSignatures.has(nodeSignature)) return false;

  const matches = extractDictionaryMatches(rawText, result);
  if (matches.length === 0) return false;

  const fragment = document.createDocumentFragment();
  let cursor = 0;
  for (const match of matches) {
    if (match.start > cursor) {
      fragment.appendChild(document.createTextNode(rawText.slice(cursor, match.start)));
    }

    const wrappedText = rawText.slice(match.start, match.end);
    const span = document.createElement("span");
    span.className = INLINE_BLUR_CLASS;
    span.textContent = wrappedText;
    span.title = `Flagged dictionary phrase: ${match.value}`;
    span.dataset.safenetPhrase = normalizeForSignature(match.value);
    bindRevealBehavior(span);
    fragment.appendChild(span);

    cursor = match.end;
  }

  if (cursor < rawText.length) {
    fragment.appendChild(document.createTextNode(rawText.slice(cursor)));
  }

  isApplyingDomMutation = true;
  try {
    textNode.replaceWith(fragment);
  } finally {
    isApplyingDomMutation = false;
  }

  parentSignatures.add(nodeSignature);
  inlineProcessedSignatures.set(parent, parentSignatures);
  return true;
}

function shouldProcessTextNode(node) {
  if (!node || node.nodeType !== Node.TEXT_NODE) return false;
  const parent = node.parentElement;
  if (!parent) return false;
  if (SKIP_PARENT_TAGS.has(parent.tagName)) return false;
  if (parent.closest(SKIP_ANCESTOR_SELECTOR)) return false;
  if (!isElementVisible(parent)) return false;
  const text = node.nodeValue || "";
  return normalizeWhitespace(text).length > 0;
}

function collapseNestedRoots(roots) {
  const collapsed = [];
  for (const root of roots) {
    if (collapsed.some((existing) => existing.contains(root))) continue;
    for (let i = collapsed.length - 1; i >= 0; i -= 1) {
      if (root.contains(collapsed[i])) {
        collapsed.splice(i, 1);
      }
    }
    collapsed.push(root);
  }
  return collapsed;
}

function getScanRoots(root = document.body) {
  if (!root || !root.isConnected) return [];
  if (root !== document.body && root !== document.documentElement) {
    return [root];
  }

  const candidates = Array.from(document.querySelectorAll(SCAN_ROOT_SELECTOR))
    .filter((element) => element.isConnected)
    .filter((element) => !element.closest(SKIP_ANCESTOR_SELECTOR))
    .filter((element) => !["BODY", "MAIN", "HTML"].includes(element.tagName))
    .filter(isElementVisible)
    .slice(0, MAX_SCAN_ROOTS);

  const roots = collapseNestedRoots(candidates);
  if (roots.length > 0) return roots;
  return [document.body];
}

function collectTextNodesFromRoot(root, remainingLimit) {
  const nodes = [];
  if (!root || remainingLimit <= 0) return nodes;

  const walker = document.createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        return shouldProcessTextNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    }
  );

  let current;
  while ((current = walker.nextNode()) && nodes.length < remainingLimit) {
    nodes.push(current);
  }
  return nodes;
}

function collectTextNodes(root = document.body, limit = MAX_TEXT_NODES_PER_SCAN) {
  const roots = getScanRoots(root);
  const nodes = [];

  for (const scanRoot of roots) {
    const remaining = limit - nodes.length;
    if (remaining <= 0) break;
    nodes.push(...collectTextNodesFromRoot(scanRoot, remaining));
  }
  return nodes;
}

async function analyzeTextWithDedupe(text) {
  const normalizedText = normalizeForSignature(text);
  const signature = `${window.location.hostname}|${normalizedText}`;
  const now = Date.now();
  const cached = analysisCache.get(signature);

  if (cached && now - cached.timestamp <= ANALYSIS_DEDUPE_WINDOW_MS) {
    return cached.result;
  }
  if (pendingTextSignatures.has(signature)) return null;
  pendingTextSignatures.add(signature);

  try {
    const response = await chrome.runtime.sendMessage({
      type: "analyzeText",
      source: "extension",
      text,
      pageUrl: window.location.href
    });
    if (!response?.ok || !response?.result) return null;
    analysisCache.set(signature, { timestamp: now, result: response.result });
    return response.result;
  } finally {
    pendingTextSignatures.delete(signature);
  }
}

async function processTextNode(textNode) {
  if (!settings?.enabled || !shouldProcessTextNode(textNode)) return;
  if (pendingNodeRequests.has(textNode)) return;

  const rawText = textNode.nodeValue || "";
  if (!shouldSendForModeration(rawText)) return;
  if (analyzedNodeText.get(textNode) === rawText) return;

  const sourceSignature = normalizeForSignature(rawText);
  const blurTarget = getBlurTargetFromTextNode(textNode);

  pendingNodeRequests.add(textNode);
  try {
    const result = await analyzeTextWithDedupe(rawText);
    if (!result) return;

    applyInlinePhraseBlur(textNode, result);

    if (blurTarget) {
      if (shouldApplyWholeMessageAction(result)) {
        applyWholeMessageBlur(blurTarget, result, sourceSignature);
      } else {
        clearWholeMessageBlur(blurTarget, sourceSignature);
      }
    }

    analyzedNodeText.set(textNode, rawText);
  } finally {
    pendingNodeRequests.delete(textNode);
  }
}

async function processNodesWithConcurrency(nodes, concurrency = ANALYZE_CONCURRENCY) {
  let index = 0;
  async function worker() {
    while (index < nodes.length) {
      const currentIndex = index;
      index += 1;
      await processTextNode(nodes[currentIndex]);
    }
  }

  const workers = [];
  for (let i = 0; i < concurrency; i += 1) {
    workers.push(worker());
  }
  await Promise.all(workers);
}

async function scanVisibleText(root = document.body) {
  if (!settings?.enabled || !document.body) return;
  cleanupAnalysisCache();
  const textNodes = collectTextNodes(root, MAX_TEXT_NODES_PER_SCAN);
  if (textNodes.length === 0) return;
  await processNodesWithConcurrency(textNodes);
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
  input.title = buildWholeMessageTooltip(result);
}

async function analyzeUserInput(input) {
  if (!settings?.enabled) return;
  const text = input.value || input.innerText || "";
  if (!shouldSendForModeration(text)) {
    clearInputModeration(input);
    return;
  }

  const result = await analyzeTextWithDedupe(text);
  if (!result) return;
  if (shouldApplyWholeMessageAction(result)) {
    applyInputModeration(input, result);
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

function queueMutationRoot(node) {
  if (!node) return;
  if (node.nodeType === Node.TEXT_NODE) {
    if (node.parentElement) pendingMutationRoots.add(node.parentElement);
    return;
  }

  if (node.nodeType === Node.ELEMENT_NODE) {
    const element = node;
    if (element.closest(`.${INLINE_BLUR_CLASS}`)) return;
    if (element.matches(SKIP_ANCESTOR_SELECTOR)) return;
    pendingMutationRoots.add(element);
  }
}

async function flushMutationQueue() {
  const roots = Array.from(pendingMutationRoots).slice(0, 40);
  pendingMutationRoots.clear();
  for (const root of roots) {
    await scanVisibleText(root);
  }
}

function initMutationObserver() {
  const observer = new MutationObserver((mutations) => {
    if (!settings?.enabled || isApplyingDomMutation) return;

    for (const mutation of mutations) {
      if (mutation.type === "childList") {
        for (const addedNode of mutation.addedNodes) {
          queueMutationRoot(addedNode);
        }
      } else if (mutation.type === "characterData") {
        queueMutationRoot(mutation.target);
      }
    }

    clearTimeout(mutationTimer);
    mutationTimer = setTimeout(() => {
      flushMutationQueue();
    }, MUTATION_DEBOUNCE_MS);
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

function bindSettingsListener() {
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "sync") return;
    settings = {
      ...(settings || {}),
      ...Object.fromEntries(Object.entries(changes).map(([key, value]) => [key, value.newValue]))
    };
  });
}

async function start() {
  injectStyles();
  await loadSettings();
  bindSettingsListener();
  bindInputListeners();
  initMutationObserver();
  await scanVisibleText(document.body);
  setInterval(() => {
    scanVisibleText(document.body);
  }, PERIODIC_SCAN_MS);
}

start();

