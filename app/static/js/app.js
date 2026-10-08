/**
 * LegalCompass — Frontend Application
 * Vanilla JS, no frameworks.
 */

// =========================================================================
// State
// =========================================================================

const State = {
  sessionId: generateId(),
  currentResult: null,
  currentCaseAnalysis: null,
  pendingContextQuestions: [],
  originalInput: "",
  loadingMessages: [
    "Detecting language…",
    "Analysing your situation…",
    "Searching legal corpus…",
    "Retrieving relevant provisions…",
    "Ranking legal evidence…",
    "Reasoning over retrieved law…",
    "Identifying relevant authority…",
    "Preparing your answer…",
  ],
  loadingMsgIdx: 0,
  loadingInterval: null,
};

function generateId() {
  return "lc_" + Math.random().toString(36).slice(2, 10);
}

// =========================================================================
// DOM helpers
// =========================================================================

function $(id) { return document.getElementById(id); }

function show(id) { $(id).style.display = ""; }
function hide(id) { $(id).style.display = "none"; }
function showFlex(id) { $(id).style.display = "flex"; }

function setText(id, text) {
  const el = $(id);
  if (el) el.textContent = text || "";
}

function setHtml(id, html) {
  const el = $(id);
  if (el) el.innerHTML = html || "";
}

function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// =========================================================================
// Input handling
// =========================================================================

document.addEventListener("DOMContentLoaded", () => {
  const input = $("userInput");
  if (!input) return;

  input.addEventListener("input", () => {
    const len = input.value.length;
    setText("charCount", `${len} / 2000`);
  });

  // Allow Ctrl+Enter to submit
  input.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "Enter") handleAnalyze();
  });
});

// =========================================================================
// Loading state
// =========================================================================

function startLoading() {

  State.isTranslated = false;
  State.englishResult = null;
  hide("languageNote");

  hide("emptyState");
  hide("resultsContent");
  hide("errorState");
  hide("contextBox");
  show("loadingState");

  $("analyzeBtn").disabled = true;
  State.loadingMsgIdx = 0;
  setText("loadingText", State.loadingMessages[0]);

  State.loadingInterval = setInterval(() => {
    State.loadingMsgIdx = (State.loadingMsgIdx + 1) % State.loadingMessages.length;
    setText("loadingText", State.loadingMessages[State.loadingMsgIdx]);
  }, 1800);
}

function stopLoading() {
  hide("loadingState");
  $("analyzeBtn").disabled = false;
  if (State.loadingInterval) {
    clearInterval(State.loadingInterval);
    State.loadingInterval = null;
  }
}

// =========================================================================
// Main analysis handler
// =========================================================================

async function handleAnalyze() {
  const message = ($("userInput").value || "").trim();
  if (!message) {
    showError("Please describe your situation before clicking Analyse.");
    return;
  }

  State.originalInput = message;
  const draftRequested = true; // always generate draft

  startLoading();

  try {
    const resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        language: "auto",
        session_id: State.sessionId,
        draft_requested: draftRequested,
      }),
    });

    const data = await resp.json();
    stopLoading();

    if (!resp.ok || data.status === "error") {
      showError("Analysis failed", data.error || "An unexpected error occurred. Please try again.");
      return;
    }

    if (data.status === "needs_context") {
      handleContextQuestions(data);
      return;
    }

    if (data.result) {
      renderResult(data.result);
    } else {
      showError("No result returned", "The analysis produced no output. Please try again.");
    }

  } catch (err) {
    stopLoading();
    showError("Connection error", "Could not reach the LegalCompass server. Please check that it is running and try again.");
    console.error(err);
  }
}

// =========================================================================
// Context questions
// =========================================================================

function handleContextQuestions(data) {
  State.pendingContextQuestions = data.context_questions || [];
  State.currentCaseAnalysis = data.case_analysis || null;

  // Show case summary if available
  if (data.case_summary) {
    show("resultsContent");
    hide("emptyState");
    $("caseSummaryBanner").style.display = "block";
    setText("caseSummaryText", data.case_summary);
    // Hide other cards
    ["card01","card02","card03","card04","card05","card06","disclaimerFooter"].forEach(hide);
  }

  // Build question inputs
  const container = $("contextQuestions");
  container.innerHTML = "";

  State.pendingContextQuestions.forEach((q, i) => {
    const div = document.createElement("div");
    div.className = "context-question";
    div.innerHTML = `
      <label for="ctxQ${i}">${escHtml(q)}</label>
      <input type="text" id="ctxQ${i}" placeholder="Your answer…" />
    `;
    container.appendChild(div);
  });

  show("contextBox");
  // Scroll to context box
  $("contextBox").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function submitContext() {
  const answers = {};
  const questionKeys = ["payment_frequency", "location", "employer_type", "unpaid_amount"];

  State.pendingContextQuestions.forEach((q, i) => {
    const val = ($(`ctxQ${i}`) || {}).value || "";
    if (val.trim()) {
      // Map question to key heuristically
      const qLower = q.toLowerCase();
      if (qLower.includes("paid") && qLower.includes("often")) {
        answers["payment_frequency"] = val.trim();
      } else if (qLower.includes("state") || qLower.includes("city") || qLower.includes("work in")) {
        answers["location"] = val.trim();
      } else if (qLower.includes("employer") || qLower.includes("type of")) {
        answers["employer_type"] = val.trim();
      } else if (qLower.includes("amount") || qLower.includes("unpaid")) {
        answers["unpaid_amount"] = val.trim();
      } else {
        answers[`context_${i}`] = val.trim();
      }
    }
  });

  if (Object.keys(answers).length === 0) {
    // Allow skipping
  }

  hide("contextBox");
  startLoading();
  setText("loadingText", "Processing your answers…");

  try {
    const resp = await fetch("/api/context", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: State.sessionId,
        original_input: State.originalInput,
        case_analysis: State.currentCaseAnalysis,
        context_answers: answers,
        draft_requested: true,
      }),
    });

    const data = await resp.json();
    stopLoading();

    if (!resp.ok || data.status === "error") {
      showError("Context processing failed", data.error || "Please try again.");
      return;
    }

    if (data.result) {
      renderResult(data.result);
    }

  } catch (err) {
    stopLoading();
    showError("Connection error", "Could not reach the server.");
    console.error(err);
  }
}

// =========================================================================
// Draft request (post-analysis)
// =========================================================================

async function requestDraft() {
  if (!State.currentResult) return;
  const result = State.currentResult;

  $("btn-draft-request") && ($("btn-draft-request").disabled = true);

  try {
    const resp = await fetch("/api/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_analysis: State.currentCaseAnalysis || {},
        selected_evidence: result.sources || [],
        authority: result.authority || {},
        document_type: "salary_notice",
      }),
    });

    const data = await resp.json();
    if (data.status === "success" && data.draft) {
      renderDraft(data.draft);
    }
  } catch (err) {
    console.error("Draft request failed:", err);
  }
}

// =========================================================================
// RENDER — main results
// =========================================================================

const SCRIPT_LANGS = [
  { re: /[\u0900-\u097F]/, code: "hi", name: "Hindi" },
  { re: /[\u0C00-\u0C7F]/, code: "te", name: "Telugu" },
  { re: /[\u0B80-\u0BFF]/, code: "ta", name: "Tamil" },
  { re: /[\u0C80-\u0CFF]/, code: "kn", name: "Kannada" },
  { re: /[\u0D00-\u0D7F]/, code: "ml", name: "Malayalam" },
  { re: /[\u0980-\u09FF]/, code: "bn", name: "Bengali" },
  { re: /[\u0A80-\u0AFF]/, code: "gu", name: "Gujarati" },
  { re: /[\u0A00-\u0A7F]/, code: "pa", name: "Punjabi" },
  { re: /[\u0B00-\u0B7F]/, code: "or", name: "Odia" },
];

function detectLangFromText(text) {
  for (const l of SCRIPT_LANGS) if (l.re.test(text || "")) return l;
  return null;
}

function resetTranslateBtn() {
  const btn = $("translateBtn");
  btn.disabled = false;
  btn.innerHTML = `Translate to <span id="translateLangName">${escHtml(State.targetLangName || "")}</span>`;
}

function renderResult(result) {
  State.currentResult = result;

  hide("emptyState");
  hide("errorState");
  hide("loadingState");
  show("resultsContent");

  // Case summary
  setText("caseSummaryText", result.case_summary || "");
  $("caseSummaryBanner").style.display = "block";

  // Language badge + translate button
  const lang = result.language || {};
let langCode = lang.code || "en";
let langName = (lang.detected && lang.detected !== "Unknown") ? lang.detected : null;

if (langCode === "en") {
  const guess = detectLangFromText(State.originalInput);
  if (guess) { langCode = guess.code; langName = guess.name; }
}

if (langCode !== "en" && langName) {
  showFlex("langBadge");
  setText("langName", langName);
  if (!State.isTranslated) showTranslateButton(langCode, langName);
} else {
  hide("translateBtn");
  hide("languageNote");
}


  // 01 — What the Law Says
  renderLawSection(result.law || {});
  show("card01");

  // 02 — How This Applies
  setText("applicationText", result.application || "");
  renderUncertainties(result.uncertainties || []);
  show("card02");

  // 03 — What You Can Do
  renderActions(result.next_steps || []);
  show("card03");

  // 04 — Authority
  renderAuthority(result.authority || {});
  show("card04");

  // 05 — Draft (always generated)
  if (result.draft_document) {
    renderDraft(result.draft_document);
    show("card05");
  } else {
    hide("card05");
  }

  // 06 — Sources
  renderSources(result.sources || []);
  show("card06");

  // Disclaimer
  setText("disclaimerFooter", result.disclaimer || "");
  show("disclaimerFooter");

  // Scroll to results
  $("resultsContent").scrollIntoView({ behavior: "smooth", block: "start" });
}

// =========================================================================
// 01 — Law section
// =========================================================================

function renderLawSection(law) {
  setText("plainSummary", law.plain_language_summary || "");

  const provisions = law.provisions || [];
  const container = $("provisions");
  container.innerHTML = "";

  provisions.forEach(prov => {
    const div = document.createElement("div");
    div.className = "provision-item";

    const sectionLabel = buildSectionLabel(prov.section, prov.section_title);
    const pageLine = prov.page ? `<span class="source-meta">Page ${prov.page}</span>` : "";
    const urlLine = prov.source_url
      ? `<a href="${escHtml(prov.source_url)}" target="_blank" rel="noopener" class="source-link">Search online ↗</a>`
      : "";

    div.innerHTML = `
      <div class="provision-doc">${escHtml(prov.document || "")}</div>
      ${sectionLabel ? `<div class="provision-section">${escHtml(sectionLabel)}</div>` : ""}
      <div class="provision-text">${escHtml(prov.plain_language || "")}</div>
      <div class="provision-meta">
        ${pageLine}
        ${urlLine}
      </div>
    `;
    container.appendChild(div);
  });
}

function buildSectionLabel(section, sectionTitle) {
  if (section && sectionTitle) return `${section} — ${sectionTitle}`;
  if (sectionTitle) return sectionTitle;
  if (section) return `Section ${section}`;
  return "";
}

// =========================================================================
// 02 — Uncertainties
// =========================================================================

function renderUncertainties(uncertainties) {
  const box = $("uncertainties");
  const items = (uncertainties || []).filter(u => u && u.trim());
  if (!items.length) {
    hide("uncertainties");
    return;
  }

  box.innerHTML = `
    <div class="uncertainty-label">⚠ Uncertainties &amp; gaps</div>
    ${items.map(u => `<div class="uncertainty-item">${escHtml(u)}</div>`).join("")}
  `;
  show("uncertainties");
}

// =========================================================================
// 03 — Actions
// =========================================================================

function renderActions(actions) {
  const list = $("actionList");
  list.innerHTML = "";

  if (!actions.length) {
    list.innerHTML = '<li class="action-item"><div class="action-text">No specific actions could be determined at this time.</div></li>';
    return;
  }

  actions.forEach((action, i) => {
    const li = document.createElement("li");
    li.className = "action-item";
    li.innerHTML = `
      <div class="action-num">${i + 1}</div>
      <div class="action-text">${escHtml(action)}</div>
    `;
    list.appendChild(li);
  });
}

// =========================================================================
// 04 — Authority
// =========================================================================

function renderAuthority(auth) {
  const body = $("authorityBody");
  if (!auth || !auth.name) {
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem;">Authority could not be determined. Please provide your location and employer type.</p>`;
    return;
  }

  const confidence = auth.confidence || "NEEDS_VERIFICATION";
  const confLabel = {
    HIGH: "✓ High Confidence",
    MEDIUM: "~ Verify Before Approaching",
    NEEDS_VERIFICATION: "! Jurisdiction Needs Verification",
  }[confidence] || confidence;

  const fields = [
    { label: "Department", value: auth.department },
    { label: "Jurisdiction", value: auth.jurisdiction },
    auth.address ? { label: "Address", value: auth.address } : null,
    auth.phone ? { label: "Phone", value: auth.phone } : null,
    auth.official_website ? {
      label: "Website",
      value: `<a href="${escHtml(auth.official_website)}" target="_blank" rel="noopener">${escHtml(auth.official_website)}</a>`,
      html: true,
    } : null,
    auth.maps_url ? {
      label: "Location",
      value: `<a href="${escHtml(auth.maps_url)}" target="_blank" rel="noopener">View on Maps ↗</a>`,
      html: true,
    } : null,
  ].filter(Boolean);

  const fieldsHtml = fields.map(f => `
    <div class="authority-field">
      <div class="af-label">${escHtml(f.label)}</div>
      <div class="af-value">${f.html ? f.value : escHtml(f.value || "")}</div>
    </div>
  `).join("");

  const verNote = auth.verification_note
    ? `<div class="verification-note">⚠ ${escHtml(auth.verification_note)}</div>`
    : "";

  const secondaryHtml = (auth.secondary_authorities || []).map(sa => {
    if (!sa || !sa.name) return "";
    return `<div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border);">
      <div class="af-label">Also consider</div>
      <div class="af-value" style="font-weight:600;">${escHtml(sa.name)}</div>
      <div class="af-value" style="font-size:0.75rem;margin-top:2px;">${escHtml(sa.reason_for_selection || "")}</div>
      ${sa.official_website ? `<div class="af-value" style="margin-top:4px;"><a href="${escHtml(sa.official_website)}" target="_blank" rel="noopener">${escHtml(sa.official_website)}</a></div>` : ""}
    </div>`;
  }).join("");

  body.innerHTML = `
    <div class="authority-card">
      <div class="confidence-badge confidence-${confidence}">${escHtml(confLabel)}</div>
      <div class="authority-name">${escHtml(auth.name)}</div>
      <div class="authority-dept">${escHtml(auth.department || "")}</div>
      <div class="authority-fields">${fieldsHtml}</div>
      ${verNote}
      <div class="authority-reason">${escHtml(auth.reason_for_selection || "")}</div>
      ${secondaryHtml}
    </div>
  `;
}

// =========================================================================
// 05 — Draft
// =========================================================================

function renderDraft(draft) {
  if (!draft) return;
  show("card05");
  setText("draftTitle", draft.title || "Draft Document");
  setText("draftText", draft.body || "");
  setText("draftDisclaimer", draft.disclaimer || "");
}

function toggleDraft() {
  const body = $("draftBody");
  const btn = $("draftToggleBtn");
  if (body.style.display === "none" || !body.style.display) {
    body.style.display = "block";
    btn.textContent = "Hide";
  } else {
    body.style.display = "none";
    btn.textContent = "Show";
  }
}

function copyDraft() {
  const text = ($("draftText") || {}).textContent || "";
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector(".btn-copy");
    if (btn) {
      btn.textContent = "✓ Copied";
      setTimeout(() => { btn.textContent = "📋 Copy Notice"; }, 2000);
    }
  }).catch(() => {
    // Fallback for older browsers
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  });
}

// =========================================================================
// 06 — Sources
// =========================================================================

function renderSources(sources) {
  const list = $("sourcesList");
  list.innerHTML = "";

  if (!sources.length) {
    list.innerHTML = '<p style="color:var(--text-muted);font-size:0.82rem;">No source documents available for this response.</p>';
    return;
  }

  sources.forEach((src, i) => {
    const sectionBadge = buildSectionLabel(
      src.section ? src.section.replace("Section ", "") : null,
      src.section_title
    );

    const div = document.createElement("div");
    div.className = "source-item";
    div.innerHTML = `
      <div class="source-header" onclick="toggleSource(${i})">
        <div class="source-doc">${escHtml(src.document || "Unknown document")}</div>
        ${sectionBadge ? `<span class="source-section-badge">${escHtml(sectionBadge)}</span>` : ""}
        <span class="source-expand-icon" id="srcIcon${i}">▼</span>
      </div>
      <div class="source-body" id="srcBody${i}">
        <div class="source-text">${escHtml(src.full_text || src.excerpt || "")}</div>
        <div class="source-footer">
          ${src.page ? `<span class="source-meta">Page ${src.page}</span>` : ""}
          ${src.source_url ? `<a href="${escHtml(src.source_url)}" target="_blank" rel="noopener" class="source-link">Search online ↗</a>` : ""}
          ${src.classification ? `<span class="source-meta">Classification: ${escHtml(src.classification)}</span>` : ""}
        </div>
      </div>
    `;
    list.appendChild(div);
  });
}

function toggleSource(idx) {
  const body = $(`srcBody${idx}`);
  const icon = $(`srcIcon${idx}`);
  if (!body) return;
  if (body.style.display === "block") {
    body.style.display = "none";
    icon && icon.classList.remove("open");
  } else {
    body.style.display = "block";
    icon && icon.classList.add("open");
  }
}

function toggleSources() {
  const body = $("sourcesBody");
  const btn = $("sourcesToggleBtn");
  if (body.style.display === "none" || !body.style.display) {
    body.style.display = "block";
    btn.textContent = "Collapse";
  } else {
    body.style.display = "none";
    btn.textContent = "Expand";
  }
}

// =========================================================================
// Error display
// =========================================================================

function showError(title, msg) {
  hide("loadingState");
  hide("emptyState");
  hide("resultsContent");

  setText("errorTitle", title || "Something went wrong");
  setText("errorMsg", msg || "Please try again.");
  show("errorState");
}

// =========================================================================
// Expose globals called from HTML onclick
// =========================================================================
window.handleAnalyze = handleAnalyze;
window.submitContext = submitContext;
window.requestDraft = requestDraft;
window.toggleDraft = toggleDraft;
window.copyDraft = copyDraft;
window.toggleSources = toggleSources;
window.toggleSource = toggleSource;
window.translateResult = translateResult;
window.showEnglish = showEnglish;

// =========================================================================
// Translation
// =========================================================================

// Store original English result so we can toggle back
State.englishResult = null;
State.targetLangCode = null;
State.targetLangName = null;
State.isTranslated = false;

function showTranslateButton(langCode, langName) {
  // Only show if non-English and Sarvam is likely available
  if (!langCode || langCode === "en") return;
  State.targetLangCode = langCode;
  State.targetLangName = langName;
  setText("translateLangName", langName);
  show("translateBtn");
}

async function translateResult() {
  if (!State.currentResult || !State.targetLangCode) return;

  const btn = $("translateBtn");
  btn.disabled = true;
  btn.textContent = "Translating…";

  try {
    const resp = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        result: State.currentResult,
        target_lang: State.targetLangCode,
        target_lang_name: State.targetLangName,
      }),
    });

    const data = await resp.json();

    if (data.status === "success" && data.translated_result) {
      // Save English version
      State.englishResult = State.currentResult;
      State.isTranslated = true;

      // Re-render with translated content
      renderResult(data.translated_result);

      // Update UI state
      resetTranslateBtn();
      hide("translateBtn");
      setText("responseLang", State.targetLangName);
      show("languageNote");

    } else {
      resetTranslateBtn();
      alert(data.error || "Translation failed.");
    }

  } catch (err) {
    resetTranslateBtn();
    console.error("Translation error:", err);
  }
}

function showEnglish() {
  if (!State.englishResult) return;
  State.isTranslated = false;
  renderResult(State.englishResult);
  setText("translateLangName", State.targetLangName);
  resetTranslateBtn();
  show("translateBtn");
  hide("languageNote");
}