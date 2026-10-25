/**
 * app.js — CrimeVision AI frontend (Phase 1)
 *
 * Vanilla JavaScript module that wires the dashboard UI to the
 * Flask REST API for:
 *   - Health status polling (GET /api/health)
 *   - Case creation (POST /api/cases)
 *   - Case listing (GET /api/cases)
 *   - Evidence upload (POST /api/cases/<id>/evidence)
 *   - Evidence listing (GET /api/cases/<id>/evidence)
 *
 * No external libraries are required beyond what is already in the DOM.
 */

"use strict";

/* ── Constants ──────────────────────────────────────────────────────────── */
const API = {
  health:        "/api/health",
  cases:         "/api/cases",
  evidence:      (cid) => `/api/cases/${cid}/evidence`,
  evidenceFile:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/file`,
  analyzeImage:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/analyze/image`,
  analyzeAudio:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/analyze/audio`,
  analyzeVideo:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/analyze/video`,
  analyzeFusion: (cid) => `/api/cases/${cid}/analyze/fusion`,
  analysis:      (cid, eid) => `/api/cases/${cid}/evidence/${eid}/analysis`,
  caseReport:    (cid) => `/api/cases/${cid}/report`,
  chat:          (cid) => `/api/cases/${cid}/chat`,
  chatHistory:   (cid) => `/api/cases/${cid}/chat/history`,
  spatialVisualization: (cid) => `/api/cases/${cid}/visualization/spatial`,
};

const MODALITY_ICONS = { image: "🖼️", audio: "🎙️", video: "📹" };

/* ── DOM references ─────────────────────────────────────────────────────── */
const dom = {
  caseSelect:        document.getElementById("case-select"),
  newCaseDetails:    document.getElementById("new-case-details"),
  newCaseName:       document.getElementById("new-case-name"),
  newCaseDesc:       document.getElementById("new-case-desc"),
  btnCreateCase:     document.getElementById("btn-create-case"),
  createCaseMsg:     document.getElementById("create-case-msg"),

  uploadZone:        document.getElementById("upload-zone"),
  fileInput:         document.getElementById("file-input"),
  uploadStatus:      document.getElementById("upload-status"),

  evidenceListSection: document.getElementById("evidence-list-section"),
  evidenceList:      document.getElementById("evidence-list"),

  healthList:        document.getElementById("health-list"),
  btnRefreshHealth:  document.getElementById("btn-refresh-health"),

  emptyState:        document.getElementById("empty-state"),
  tabPanels:         document.getElementById("tab-panels"),
  tabBtns:           document.querySelectorAll(".tab-btn"),

  panelImage:        document.getElementById("panel-image"),
  panelAudio:        document.getElementById("panel-audio"),
  panelVideo:        document.getElementById("panel-video"),
  panelFusion:       document.getElementById("panel-fusion"),

  evidenceImage:     document.getElementById("evidence-image"),
  evidenceAudio:     document.getElementById("evidence-audio"),
  evidenceVideo:     document.getElementById("evidence-video"),
  bboxCanvas:        document.getElementById("bbox-canvas"),

  // Phase 2 Image Analysis Controls & Findings
  btnRunImageAnalysis: document.getElementById("btn-run-image-analysis"),
  imageStatusBadge:    document.getElementById("image-status-badge"),
  rtdetrCountBadge:    document.getElementById("rtdetr-count-badge"),
  rtdetrContent:       document.getElementById("rtdetr-content"),
  blipContent:         document.getElementById("blip-content"),
  clipContent:         document.getElementById("clip-content"),

  // Phase 4 Audio Analysis Controls & Findings
  btnRunAudioAnalysis: document.getElementById("btn-run-audio-analysis"),
  audioStatusBadge:    document.getElementById("audio-status-badge"),
  whisperLangBadge:    document.getElementById("whisper-lang-badge"),
  whisperContent:      document.getElementById("whisper-content"),
  audioTranscriptContainer: document.getElementById("audio-transcript-container"),
  audioSegmentsList:   document.getElementById("audio-segments-list"),
  audioEmptyPlaceholder: document.getElementById("audio-empty-placeholder"),

  // Phase 5 Video Analysis Controls & Findings
  btnRunVideoAnalysis:  document.getElementById("btn-run-video-analysis"),
  videoSampleInterval:  document.getElementById("video-sample-interval"),
  videoStatusBadge:     document.getElementById("video-status-badge"),
  videoCountBadge:      document.getElementById("video-count-badge"),
  videoContent:         document.getElementById("video-content"),
  videoTimelineContainer: document.getElementById("video-timeline-container"),
  videoFramesList:      document.getElementById("video-frames-list"),
  videoEmptyPlaceholder: document.getElementById("video-empty-placeholder"),

  // Phase 6 Multimodal Fusion Controls & Elements
  btnRunFusion:         document.getElementById("btn-run-fusion"),
  fusionStatusBadge:    document.getElementById("fusion-status-badge"),
  covImgBadge:          document.getElementById("cov-img-badge"),
  covAudBadge:          document.getElementById("cov-aud-badge"),
  covVidBadge:          document.getElementById("cov-vid-badge"),
  fusionScopeSummary:   document.getElementById("fusion-scope-summary"),
  fusionAssocCount:     document.getElementById("fusion-assoc-count"),
  fusionAssociationsContent: document.getElementById("fusion-associations-content"),
  fusionTemporalCount:  document.getElementById("fusion-temporal-count"),
  fusionTemporalContent: document.getElementById("fusion-temporal-content"),
  fusionConflictCount:  document.getElementById("fusion-conflict-count"),
  fusionContradictionsContent: document.getElementById("fusion-contradictions-content"),
  fusionQuestionsContent: document.getElementById("fusion-questions-content"),

  btnDownloadPdf:    document.getElementById("btn-download-pdf"),
  toastContainer:    document.getElementById("toast-container"),

  // Phase 7 Forensic AI Chat Assistant
  chatDrawer:        document.getElementById("chat-drawer"),
  chatMessages:      document.getElementById("chat-messages"),
  chatEmptyHint:     document.getElementById("chat-empty-hint"),
  chatForm:          document.getElementById("chat-form"),
  chatInput:         document.getElementById("chat-input"),
  btnChatSend:       document.getElementById("btn-chat-send"),
  chatSendText:      document.getElementById("chat-send-text"),
  chatSendSpinner:   document.getElementById("chat-send-spinner"),
  btnClearChat:      document.getElementById("btn-clear-chat"),
  chatStatusBadge:   document.getElementById("chat-status-badge"),
  chatSuggestions:   document.getElementById("chat-suggestions"),

  // Phase 8 3D Spatial Scene
  panelScene3d:          document.getElementById("panel-scene3d"),
  scene3dViewport:       document.getElementById("scene3d-viewport"),
  threejsCanvas:         document.getElementById("threejs-canvas"),
  scene3dEmptyState:     document.getElementById("scene3d-empty-state"),
  scene3dEmptyText:      document.getElementById("scene3d-empty-text"),
  scene3dLoading:        document.getElementById("scene3d-loading"),
  scene3dLegend:         document.getElementById("scene3d-legend"),
  scene3dLegendList:     document.getElementById("scene3d-legend-list"),
  scene3dDetailsCard:    document.getElementById("scene3d-details-card"),
  btnScene3dResetCam:    document.getElementById("btn-scene3d-reset-cam"),
  btnScene3dToggleGrid:  document.getElementById("btn-scene3d-toggle-grid"),
  btnScene3dToggleLabels:document.getElementById("btn-scene3d-toggle-labels"),
  btnScene3dRefresh:     document.getElementById("btn-scene3d-refresh"),
  scene3dFilterCategory: document.getElementById("scene3d-filter-category"),
  scene3dFilterEvidence: document.getElementById("scene3d-filter-evidence"),
  scene3dConfSlider:     document.getElementById("scene3d-conf-slider"),
  scene3dConfVal:        document.getElementById("scene3d-conf-val"),
  scene3dCountBadge:     document.getElementById("scene3d-count-badge"),
  detCardLabel:          document.getElementById("det-card-label"),
  detCardConf:           document.getElementById("det-card-conf"),
  detCardEvidence:       document.getElementById("det-card-evidence"),
  detCardTimestampRow:   document.getElementById("det-card-timestamp-row"),
  detCardTimestamp:      document.getElementById("det-card-timestamp"),
  detCardBbox:           document.getElementById("det-card-bbox"),
  detCardPos:            document.getElementById("det-card-pos"),
  btnCloseDetCard:       document.getElementById("btn-close-det-card"),
  btnDetCardNavigate:    document.getElementById("btn-det-card-navigate"),
  workspaceCaseName:     document.getElementById("workspace-case-name"),
};

/* ── App state ──────────────────────────────────────────────────────────── */
const state = {
  activeCaseId:     null,
  activeEvidenceId: null,
  cases:            [],
  evidence:         [],
};

/* ══════════════════════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
════════════════════════════════════════════════════════════════════════════ */
function showToast(message, type = "info", durationMs = 4000) {
  const ICONS = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.setAttribute("role", "status");
  toast.innerHTML = `<span aria-hidden="true">${ICONS[type] || "ℹ️"}</span> ${escapeHtml(message)}`;
  dom.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(20px)";
    toast.style.transition = "opacity 250ms ease, transform 250ms ease";
    setTimeout(() => toast.remove(), 260);
  }, durationMs);
}

/* ══════════════════════════════════════════════════════════════════════════
   UTILITY
════════════════════════════════════════════════════════════════════════════ */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  if (match && match[1]) return decodeURIComponent(match[1]);
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? (meta.getAttribute('content') || meta.content || '') : '';
}

async function apiFetch(url, options = {}) {
  try {
    const opts = { ...options };
    const method = (opts.method || "GET").toUpperCase();
    opts.headers = opts.headers ? { ...opts.headers } : {};

    // Attach CSRF token on state-changing requests
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      const csrf = getCsrfToken();
      if (csrf) {
        if (!opts.headers["X-CSRF-Token"] && !opts.headers["X-CSRFToken"]) {
          opts.headers["X-CSRF-Token"] = csrf;
        }
        if (opts.body instanceof FormData && !opts.body.has("csrf_token")) {
          opts.body.append("csrf_token", csrf);
        }
      }
    }

    // Never manually specify Content-Type for FormData; browser must calculate multipart boundary
    if (opts.body instanceof FormData) {
      delete opts.headers["Content-Type"];
      delete opts.headers["content-type"];
    }

    const res = await fetch(url, opts);
    if (res.status === 401) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
      return { ok: false, status: 401, data: { error: "Authentication required." } };
    }
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: { error: err.message } };
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   HEALTH CHECK
════════════════════════════════════════════════════════════════════════════ */
async function refreshHealth() {
  dom.healthList.innerHTML = `<li class="health-item health-item--loading">Checking…</li>`;
  try {
    const { ok, data } = await apiFetch(API.health);
    if (!ok) throw new Error("Non-OK response");

    const rows = [];
    const checks = data.checks || {};

    // Service status
    const svcClass = data.status === "ok" ? "ok" : "warn";
    rows.push(renderHealthItem("service", data.status || "unknown", svcClass));

    // Individual checks
    for (const [key, value] of Object.entries(checks)) {
      const cls = value === "ok" || value === "configured"
        ? "ok"
        : value === "not_configured"
          ? "warn"
          : "error";
      rows.push(renderHealthItem(key, value, cls));
    }

    dom.healthList.innerHTML = rows.join("");
  } catch (err) {
    dom.healthList.innerHTML = `<li class="health-item"><span class="health-item__value health-item__value--error">Unreachable</span></li>`;
  }
}

function renderHealthItem(key, value, cls) {
  return `
    <li class="health-item">
      <span class="health-item__key">${escapeHtml(key)}</span>
      <span class="health-item__value health-item__value--${cls}">${escapeHtml(value)}</span>
    </li>`;
}

/* ══════════════════════════════════════════════════════════════════════════
   CASE MANAGEMENT
════════════════════════════════════════════════════════════════════════════ */
async function loadCases() {
  const { ok, data } = await apiFetch(API.cases);
  if (!ok) return;
  state.cases = data.cases || [];
  renderCaseSelect();
}

function renderCaseSelect() {
  const prev = dom.caseSelect.value;
  dom.caseSelect.innerHTML = `<option value="">— Select or create —</option>`;

  const visibleCases = (state.cases || []).filter(c => !c.is_readonly && c.case_id !== "case_demo_sentinel" && c.demo_type !== "legacy" && !c.is_demo);
  for (const c of visibleCases) {
    const opt = document.createElement("option");
    opt.value = c.case_id;
    opt.textContent = `${c.name} (${c.case_id})`;
    dom.caseSelect.appendChild(opt);
  }

  // Restore prior selection if still available
  if (prev && visibleCases.find((c) => c.case_id === prev)) {
    dom.caseSelect.value = prev;
  }
}

async function createCase() {
  const name = dom.newCaseName.value.trim();
  if (!name) {
    dom.createCaseMsg.textContent = "Case name is required.";
    dom.createCaseMsg.className = "form-hint status-msg--error";
    return;
  }

  dom.btnCreateCase.disabled = true;
  dom.createCaseMsg.textContent = "Creating…";
  dom.createCaseMsg.className = "form-hint";

  const { ok, data } = await apiFetch(API.cases, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      description: dom.newCaseDesc.value.trim(),
    }),
  });

  dom.btnCreateCase.disabled = false;

  if (!ok) {
    const msg = data.error || "Failed to create case.";
    dom.createCaseMsg.textContent = msg;
    dom.createCaseMsg.className = "form-hint status-msg--error";
    showToast(msg, "error");
    return;
  }

  const created = data.case;
  dom.createCaseMsg.textContent = `Case created: ${created.case_id}`;
  dom.createCaseMsg.className = "form-hint status-msg--ok";
  dom.newCaseName.value = "";
  dom.newCaseDesc.value = "";

  await loadCases();
  dom.caseSelect.value = created.case_id;
  await selectCase(created.case_id);

  showToast(`Case "${created.name}" created successfully.`, "success");
  dom.newCaseDetails.removeAttribute("open");
}

async function selectCase(caseId) {
  state.activeCaseId = caseId || null;

  if (!caseId) {
    if (dom.workspaceCaseName) dom.workspaceCaseName.textContent = "No Active Case Selected";
    state.evidence = [];
    renderEvidenceList();
    showEmptyState();
    if (dom.btnDownloadPdf) dom.btnDownloadPdf.disabled = true;
    resetFusionFindings();
    resetChatAssistant();
    resetScene3d();
    return;
  }

  const selectedCase = state.cases.find(c => c.case_id === caseId);
  if (dom.workspaceCaseName) {
    dom.workspaceCaseName.textContent = selectedCase ? `${selectedCase.name} (${selectedCase.case_id})` : caseId;
  }

  if (dom.btnDownloadPdf) dom.btnDownloadPdf.disabled = false;
  resetFusionFindings();
  resetScene3d();
  await loadEvidence(caseId);
  await loadChatHistory(caseId);

  const activeTabBtn = document.querySelector(".tab-btn--active");
  if (activeTabBtn && activeTabBtn.dataset.tab === "scene3d") {
    await loadScene3d(caseId);
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   PHASE 3 PDF FORENSIC REPORT GENERATION
════════════════════════════════════════════════════════════════════════════ */
async function downloadForensicPdf() {
  if (!state.activeCaseId) {
    showToast("Please select a case before generating a PDF report.", "warning");
    return;
  }

  dom.btnDownloadPdf.disabled = true;
  dom.btnDownloadPdf.innerHTML = `<span class="spin-loader">↻</span> Generating PDF…`;
  showToast("Compiling forensic report with ReportLab…", "info");

  try {
    const payload = {};
    if (state.activeEvidenceId) {
      payload.evidence_id = state.activeEvidenceId;
    }

    const { ok, status, data } = await apiFetch(API.caseReport(state.activeCaseId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!ok) {
      const err = data.error || "Report generation failed.";
      showToast(err, "error");
      return;
    }

    const rep = data.report;
    showToast(`Report generated (${formatBytes(rep.file_size)}). Downloading…`, "success");

    // Trigger browser download via anchor click
    const a = document.createElement("a");
    a.href = rep.download_url;
    a.download = rep.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    showToast(`Error requesting report: ${err}`, "error");
  } finally {
    dom.btnDownloadPdf.disabled = false;
    dom.btnDownloadPdf.innerHTML = `⬇ Download PDF Report`;
  }
}


/* ══════════════════════════════════════════════════════════════════════════
   EVIDENCE
════════════════════════════════════════════════════════════════════════════ */
async function loadEvidence(caseId) {
  const { ok, data } = await apiFetch(API.evidence(caseId));
  if (!ok) {
    showToast("Could not load evidence list.", "error");
    return;
  }
  state.evidence = data.evidence || [];
  renderEvidenceList();
}

function renderEvidenceList() {
  if (state.evidence.length === 0) {
    dom.evidenceListSection.style.display = "none";
    showEmptyState();
    return;
  }

  dom.evidenceListSection.style.display = "block";
  dom.evidenceList.innerHTML = state.evidence
    .map((ev) => {
      const icon = MODALITY_ICONS[ev.modality] || "📄";
      const active = ev.evidence_id === state.activeEvidenceId ? " evidence-item--active" : "";
      return `
        <li class="evidence-item${active}" data-evidence-id="${escapeHtml(ev.evidence_id)}"
            data-modality="${escapeHtml(ev.modality)}" role="listitem" tabindex="0"
            title="${escapeHtml(ev.original_name)} (${escapeHtml(ev.sha256.slice(0, 12))}…)">
          <span class="evidence-item__icon">${icon}</span>
          <span class="evidence-item__name">${escapeHtml(ev.original_name)}</span>
          <span class="evidence-item__modality">${escapeHtml(ev.modality)}</span>
        </li>`;
    })
    .join("");

  // Event delegation
  dom.evidenceList.querySelectorAll(".evidence-item").forEach((li) => {
    li.addEventListener("click", () => selectEvidence(li.dataset.evidenceId, li.dataset.modality));
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") selectEvidence(li.dataset.evidenceId, li.dataset.modality);
    });
  });
}

function selectEvidence(evidenceId, modality) {
  state.activeEvidenceId = evidenceId;
  renderEvidenceList(); // refresh active highlight

  const ev = state.evidence.find((e) => e.evidence_id === evidenceId);
  if (!ev) return;

  showTabPanels();
  activateTab(modality || "image");

  // Show media preview — file access is served via a dedicated route
  // (Phase 1: we render metadata only; actual file serving is Phase 2+)
  setViewportContent(ev);
}

function setViewportContent(ev) {
  // Hide all media elements first
  dom.evidenceImage.style.display = "none";
  dom.bboxCanvas.style.display = "none";
  dom.evidenceAudio.style.display = "none";
  dom.evidenceVideo.style.display = "none";

  if (!ev) return;

  if (ev.modality === "image") {
    const fileUrl = API.evidenceFile(ev.case_id, ev.evidence_id);
    dom.evidenceImage.crossOrigin = "anonymous";
    dom.evidenceImage.src = fileUrl;
    dom.evidenceImage.style.display = "block";

    dom.btnRunImageAnalysis.disabled = false;
    dom.btnRunImageAnalysis.style.display = "inline-flex";

    // If analysis already exists on the record, render findings & bounding boxes
    if (ev.analysis_json) {
      renderImageFindings(ev.analysis_json);
      dom.evidenceImage.onload = () => {
        drawBoundingBoxes(ev.analysis_json);
      };
    } else {
      resetImageFindings();
      clearCanvas();
    }
  } else if (ev.modality === "audio") {
    const fileUrl = API.evidenceFile(ev.case_id, ev.evidence_id);
    dom.evidenceAudio.src = fileUrl;
    dom.evidenceAudio.style.display = "block";

    if (dom.btnRunAudioAnalysis) {
      dom.btnRunAudioAnalysis.disabled = false;
      dom.btnRunAudioAnalysis.style.display = "inline-flex";
    }

    if (ev.analysis_json && ev.analysis_json.audio) {
      renderAudioFindings(ev.analysis_json);
    } else {
      resetAudioFindings();
    }
    clearCanvas();
  } else if (ev.modality === "video") {
    const fileUrl = API.evidenceFile(ev.case_id, ev.evidence_id);
    dom.evidenceVideo.src = fileUrl;
    dom.evidenceVideo.style.display = "block";

    if (dom.btnRunVideoAnalysis) {
      dom.btnRunVideoAnalysis.disabled = false;
      dom.btnRunVideoAnalysis.style.display = "inline-flex";
    }

    if (ev.analysis_json && ev.analysis_json.video) {
      renderVideoFindings(ev.analysis_json);
    } else {
      resetVideoFindings();
    }
    clearCanvas();
  } else {
    dom.btnRunImageAnalysis.disabled = true;
    dom.btnRunImageAnalysis.style.display = "none";
    if (dom.btnRunAudioAnalysis) {
      dom.btnRunAudioAnalysis.disabled = true;
      dom.btnRunAudioAnalysis.style.display = "none";
    }
    if (dom.btnRunVideoAnalysis) {
      dom.btnRunVideoAnalysis.disabled = true;
      dom.btnRunVideoAnalysis.style.display = "none";
    }
    clearCanvas();
    resetImageFindings();
    resetAudioFindings();
    resetVideoFindings();
  }
}

function clearCanvas() {
  const canvas = dom.bboxCanvas;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  canvas.style.display = "none";
}

function resetImageFindings() {
  dom.rtdetrCountBadge.style.display = "none";
  dom.rtdetrContent.innerHTML = `<p class="finding-block__body muted">Click 'Run Image Analysis' to detect objects.</p>`;
  dom.blipContent.innerHTML = `<p class="finding-block__body muted">Scene captioning pending analysis.</p>`;
  dom.clipContent.innerHTML = `<p class="finding-block__body muted">Zero-shot forensic scene similarity pending analysis.</p>`;
  dom.imageStatusBadge.textContent = "Image Analysis Ready";
  dom.imageStatusBadge.className = "panel-notice badge badge--cobalt";
}

function resetAudioFindings() {
  if (dom.whisperLangBadge) dom.whisperLangBadge.style.display = "none";
  if (dom.whisperContent) {
    dom.whisperContent.innerHTML = `<p class="finding-block__body muted">Select an audio file and click 'Run Audio Transcription'.</p>`;
  }
  if (dom.audioTranscriptContainer) dom.audioTranscriptContainer.style.display = "none";
  if (dom.audioSegmentsList) dom.audioSegmentsList.innerHTML = "";
  if (dom.audioStatusBadge) {
    dom.audioStatusBadge.textContent = "Audio Analysis Ready";
    dom.audioStatusBadge.className = "panel-notice badge badge--cobalt";
  }
}

function renderAudioFindings(analysis) {
  if (!analysis) return;
  const audioRes = analysis.audio || {};
  const meta = audioRes.audio_metadata || {};
  const transcript = audioRes.transcript || "";
  const segments = audioRes.segments || [];
  const lang = audioRes.language || "unknown";

  if (audioRes.status === "success") {
    if (dom.whisperLangBadge) {
      dom.whisperLangBadge.textContent = lang.toUpperCase();
      dom.whisperLangBadge.style.display = "inline-flex";
    }

    if (dom.whisperContent) {
      let durStr = meta.duration_seconds ? `${meta.duration_seconds.toFixed(2)}s` : "N/A";
      let srStr = meta.sample_rate ? `${meta.sample_rate} Hz` : "16000 Hz";
      dom.whisperContent.innerHTML = `
        <div style="margin-bottom: 8px;">
          <p class="forensic-caption-quote">"${escapeHtml(transcript || 'No speech detected.')}"</p>
          <p class="muted mono" style="font-size: 10px; margin-top: 4px;">Duration: ${durStr} · Sample Rate: ${srStr} · Lang: ${escapeHtml(lang.toUpperCase())}</p>
        </div>
        <p class="form-hint" style="font-size: 10px; color: #94A3B8;">${escapeHtml(audioRes.forensic_notice || '')}</p>
      `;
    }

    // Render timeline segments in viewport
    if (dom.audioTranscriptContainer && dom.audioSegmentsList) {
      if (segments.length > 0) {
        dom.audioSegmentsList.innerHTML = segments.map(seg => {
          const s = seg.start_seconds !== null ? seg.start_seconds.toFixed(2) : "0.00";
          const e = seg.end_seconds !== null ? seg.end_seconds.toFixed(2) : "0.00";
          return `
            <div class="segment-row" style="padding: 6px 10px; border-bottom: 1px solid #334155; cursor: pointer; display: flex; gap: 12px; align-items: baseline;"
                 onclick="seekAudio(${seg.start_seconds || 0})">
              <span class="badge badge--cobalt badge--xs mono">[${s}s - ${e}s]</span>
              <span class="segment-text" style="color: #E2E8F0; font-size: 13px;">${escapeHtml(seg.text)}</span>
            </div>
          `;
        }).join("");
        dom.audioTranscriptContainer.style.display = "block";
      } else {
        dom.audioSegmentsList.innerHTML = `<p class="muted" style="padding: 8px;">No timestamped segments found.</p>`;
        dom.audioTranscriptContainer.style.display = "block";
      }
    }

    if (dom.audioStatusBadge) {
      dom.audioStatusBadge.textContent = "Transcription Complete";
      dom.audioStatusBadge.className = "panel-notice badge badge--emerald";
    }
  } else if (audioRes.status === "failed") {
    if (dom.whisperLangBadge) dom.whisperLangBadge.style.display = "none";
    if (dom.whisperContent) {
      dom.whisperContent.innerHTML = `<p class="finding-block__body status-msg--error">Whisper error: ${escapeHtml(audioRes.error || 'Transcription Failed')}</p>`;
    }
    if (dom.audioStatusBadge) {
      dom.audioStatusBadge.textContent = "Transcription Failed";
      dom.audioStatusBadge.className = "panel-notice badge badge--crimson";
    }
  }
}

function seekAudio(seconds) {
  if (dom.evidenceAudio && !isNaN(seconds)) {
    dom.evidenceAudio.currentTime = seconds;
    dom.evidenceAudio.play().catch(() => {});
  }
}
window.seekAudio = seekAudio;

async function runAudioTranscription() {
  if (!state.activeCaseId || !state.activeEvidenceId) {
    showToast("Please select an audio evidence item first.", "warning");
    return;
  }

  const ev = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
  if (!ev || ev.modality !== "audio") {
    showToast("Selected item is not an audio file.", "warning");
    return;
  }

  dom.btnRunAudioAnalysis.disabled = true;
  dom.btnRunAudioAnalysis.innerHTML = `<span class="spin-loader">↻</span> Transcribing…`;
  if (dom.audioStatusBadge) {
    dom.audioStatusBadge.textContent = "Running OpenAI Whisper Speech-to-Text…";
    dom.audioStatusBadge.className = "panel-notice badge badge--amber";
  }

  showToast("Starting audio transcription with Whisper Base…", "info");

  const { ok, status, data } = await apiFetch(API.analyzeAudio(state.activeCaseId, state.activeEvidenceId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

  dom.btnRunAudioAnalysis.disabled = false;
  dom.btnRunAudioAnalysis.innerHTML = `🎙️ Run Audio Transcription`;

  if (!ok) {
    const errMsg = data.error || "Audio transcription failed.";
    showToast(errMsg, "error");
    if (dom.audioStatusBadge) {
      dom.audioStatusBadge.textContent = "Transcription Failed";
      dom.audioStatusBadge.className = "panel-notice badge badge--crimson";
    }
    return;
  }

  const analysis = data.analysis;
  ev.analysis_json = analysis;
  ev.analysis_status = data.status || "completed";

  renderAudioFindings(analysis);
  showToast("Audio transcription completed successfully.", "success");
}

function resetVideoFindings() {
  if (dom.videoCountBadge) dom.videoCountBadge.style.display = "none";
  if (dom.videoContent) {
    dom.videoContent.innerHTML = `<p class="finding-block__body muted">Select a video and click 'Run Video Analysis'.</p>`;
  }
  if (dom.videoTimelineContainer) dom.videoTimelineContainer.style.display = "none";
  if (dom.videoFramesList) dom.videoFramesList.innerHTML = "";
  if (dom.videoStatusBadge) {
    dom.videoStatusBadge.textContent = "Video Analysis Ready";
    dom.videoStatusBadge.className = "panel-notice badge badge--cobalt";
  }
}

function renderVideoFindings(analysis) {
  if (!analysis) return;
  const vidRes = analysis.video || {};
  const meta = vidRes.video_metadata || {};
  const agg = vidRes.aggregated_detections || {};
  const sampled = vidRes.sampled_frames || [];
  const status = vidRes.status || analysis.status || "completed";

  if (status === "completed" || status === "partial" || status === "success") {
    const totalDet = agg.total_detections || 0;
    if (dom.videoCountBadge) {
      dom.videoCountBadge.textContent = `${totalDet} detections`;
      dom.videoCountBadge.style.display = "inline-flex";
    }

    if (dom.videoContent) {
      let durStr = meta.duration_seconds ? `${meta.duration_seconds.toFixed(2)}s` : "N/A";
      let resStr = meta.width && meta.height ? `${meta.width}x${meta.height}` : "N/A";
      let fpsStr = meta.fps ? `${meta.fps.toFixed(1)} fps` : "N/A";

      let classListHtml = "";
      if (agg.class_counts && Object.keys(agg.class_counts).length > 0) {
        classListHtml = `<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px;">` +
          Object.entries(agg.class_counts).map(([cls, cnt]) => `
            <span class="badge badge--cobalt badge--xs">${escapeHtml(cls)} (${cnt})</span>
          `).join("") + `</div>`;
      }

      dom.videoContent.innerHTML = `
        <div style="margin-bottom: 8px;">
          <p class="muted mono" style="font-size: 11px;">
            Duration: ${durStr} · Res: ${resStr} · FPS: ${fpsStr}
          </p>
          <p style="font-size: 12px; margin-top: 4px; color: #E2E8F0;">
            Analyzed <b>${sampled.length}</b> sampled frame(s). Detected <b>${totalDet}</b> object instances.
          </p>
          ${classListHtml}
        </div>
        <p class="form-hint" style="font-size: 10px; color: #94A3B8;">${escapeHtml(vidRes.forensic_notice || '')}</p>
      `;
    }

    // Render timeline frames in viewport
    if (dom.videoTimelineContainer && dom.videoFramesList) {
      if (sampled.length > 0) {
        dom.videoFramesList.innerHTML = sampled.map(sf => {
          const t = sf.timestamp_seconds !== undefined ? sf.timestamp_seconds.toFixed(2) : "0.00";
          const fIdx = sf.frame_index !== undefined ? sf.frame_index : 0;
          const objs = sf.objects || [];

          let objText = objs.map(o => `${escapeHtml(o.label)} (${(o.confidence * 100).toFixed(0)}%)`).join(", ");
          if (!objText) {
            objText = sf.status === "failed" ? `<font color="#EF4444">Failed: ${escapeHtml(sf.error || 'Error')}</font>` : "<i>No objects detected</i>";
          }

          return `
            <div class="frame-row" style="padding: 6px 10px; border-bottom: 1px solid #334155; cursor: pointer; display: flex; gap: 12px; align-items: baseline; background: #1E293B; border-radius: 4px;"
                 onclick="seekVideo(${sf.timestamp_seconds || 0})">
              <span class="badge badge--cobalt badge--xs mono" style="white-space: nowrap;">[${t}s · frame #${fIdx}]</span>
              <span class="frame-detections" style="color: #E2E8F0; font-size: 12px;">${objText}</span>
            </div>
          `;
        }).join("");
        dom.videoTimelineContainer.style.display = "block";
      } else {
        dom.videoFramesList.innerHTML = `<p class="muted" style="padding: 8px;">No sampled frames found.</p>`;
        dom.videoTimelineContainer.style.display = "block";
      }
    }

    if (dom.videoStatusBadge) {
      dom.videoStatusBadge.textContent = status === "partial" ? "Analysis Partial" : "Analysis Complete";
      dom.videoStatusBadge.className = status === "partial" ? "panel-notice badge badge--amber" : "panel-notice badge badge--emerald";
    }
  } else if (status === "failed") {
    if (dom.videoCountBadge) dom.videoCountBadge.style.display = "none";
    if (dom.videoContent) {
      dom.videoContent.innerHTML = `<p class="finding-block__body status-msg--error">Video analysis error: ${escapeHtml(vidRes.error || 'Analysis Failed')}</p>`;
    }
    if (dom.videoStatusBadge) {
      dom.videoStatusBadge.textContent = "Analysis Failed";
      dom.videoStatusBadge.className = "panel-notice badge badge--crimson";
    }
  }
}

function seekVideo(seconds) {
  if (dom.evidenceVideo && !isNaN(seconds)) {
    dom.evidenceVideo.currentTime = seconds;
    dom.evidenceVideo.play().catch(() => {});
  }
}
window.seekVideo = seekVideo;

async function runVideoAnalysis() {
  if (!state.activeCaseId || !state.activeEvidenceId) {
    showToast("Please select a video evidence item first.", "warning");
    return;
  }

  const ev = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
  if (!ev || ev.modality !== "video") {
    showToast("Selected item is not a video file.", "warning");
    return;
  }

  const sampleInterval = dom.videoSampleInterval ? parseFloat(dom.videoSampleInterval.value) || 1.0 : 1.0;

  dom.btnRunVideoAnalysis.disabled = true;
  dom.btnRunVideoAnalysis.innerHTML = `<span class="spin-loader">↻</span> Analyzing…`;
  if (dom.videoStatusBadge) {
    dom.videoStatusBadge.textContent = "Sampling frames & running RT-DETR…";
    dom.videoStatusBadge.className = "panel-notice badge badge--amber";
  }

  showToast(`Extracting video frames (interval: ${sampleInterval}s) & analyzing with RT-DETR…`, "info");

  const { ok, status, data } = await apiFetch(API.analyzeVideo(state.activeCaseId, state.activeEvidenceId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sample_interval_seconds: sampleInterval }),
  });

  dom.btnRunVideoAnalysis.disabled = false;
  dom.btnRunVideoAnalysis.innerHTML = `🎬 Run Video Analysis`;

  if (!ok) {
    const errMsg = data.error || "Video analysis failed.";
    showToast(errMsg, "error");
    if (dom.videoStatusBadge) {
      dom.videoStatusBadge.textContent = "Analysis Failed";
      dom.videoStatusBadge.className = "panel-notice badge badge--crimson";
    }
    return;
  }

  const analysis = data.analysis;
  ev.analysis_json = analysis;
  ev.analysis_status = data.status || "completed";

  renderVideoFindings(analysis);
  showToast("Video frame analysis completed successfully.", "success");
}

/* ══════════════════════════════════════════════════════════════════════════
   PHASE 6 MULTIMODAL EVIDENCE FUSION
════════════════════════════════════════════════════════════════════════════ */
function resetFusionFindings() {
  if (dom.fusionStatusBadge) {
    dom.fusionStatusBadge.textContent = "Multimodal Fusion Ready";
    dom.fusionStatusBadge.className = "panel-notice badge badge--cobalt";
  }
  if (dom.covImgBadge) dom.covImgBadge.textContent = "Image: Pending";
  if (dom.covAudBadge) dom.covAudBadge.textContent = "Audio: Pending";
  if (dom.covVidBadge) dom.covVidBadge.textContent = "Video: Pending";
  if (dom.fusionScopeSummary) dom.fusionScopeSummary.textContent = "Select an active case and run analysis across modalities.";
  if (dom.fusionAssocCount) dom.fusionAssocCount.style.display = "none";
  if (dom.fusionAssociationsContent) {
    dom.fusionAssociationsContent.innerHTML = `<p class="finding-block__body muted">Click 'Synthesize Multimodal Fusion' to cross-reference entities across image and video evidence.</p>`;
  }
  if (dom.fusionTemporalCount) dom.fusionTemporalCount.style.display = "none";
  if (dom.fusionTemporalContent) {
    dom.fusionTemporalContent.innerHTML = `<p class="finding-block__body muted">Temporal speech-to-video associations will appear when audio and video have been transcribed and sampled.</p>`;
  }
  if (dom.fusionConflictCount) dom.fusionConflictCount.style.display = "none";
  if (dom.fusionContradictionsContent) {
    dom.fusionContradictionsContent.innerHTML = `<p class="finding-block__body muted">Any contradictory scene descriptions or environmental divergences will be flagged for human examiner review.</p>`;
  }
  if (dom.fusionQuestionsContent) {
    dom.fusionQuestionsContent.innerHTML = `<p class="finding-block__body muted">Identified evidence gaps and unanalyzed channels will be outlined here.</p>`;
  }
}

function renderFusionFindings(fusion) {
  if (!fusion) return;

  const cov = fusion.modality_coverage || {};
  const assocs = fusion.cross_modal_associations || [];
  const tempAssocs = fusion.temporal_associations || [];
  const conflicts = fusion.potential_contradictions || [];
  const questions = fusion.unresolved_questions || [];

  // Update Status Badge
  if (dom.fusionStatusBadge) {
    const st = fusion.status;
    let badgeText = "Fusion Complete";
    let badgeClass = "panel-notice badge badge--emerald";
    if (st === "single_modality") {
      badgeText = "Single Modality Analyzed";
      badgeClass = "panel-notice badge badge--amber";
    } else if (st === "partial") {
      badgeText = "Partial Modality Fusion";
      badgeClass = "panel-notice badge badge--amber";
    } else if (st === "empty" || st === "pending") {
      badgeText = "Analysis Pending";
      badgeClass = "panel-notice badge badge--slate";
    }
    dom.fusionStatusBadge.textContent = badgeText;
    dom.fusionStatusBadge.className = badgeClass;
  }

  // Update Coverage Badges
  const updateCovBadge = (el, modName) => {
    if (!el) return;
    const info = cov[modName] || {};
    const status = info.status || "unavailable";
    let colorClass = "badge--slate";
    if (status === "analyzed") colorClass = "badge--emerald";
    else if (status === "partial") colorClass = "badge--amber";
    else if (status === "pending") colorClass = "badge--crimson";
    el.textContent = `${modName.charAt(0).toUpperCase() + modName.slice(1)}: ${status.toUpperCase()} (${info.analyzed || 0}/${info.total || 0})`;
    el.className = `badge ${colorClass} badge--xs`;
  };

  updateCovBadge(dom.covImgBadge, "image");
  updateCovBadge(dom.covAudBadge, "audio");
  updateCovBadge(dom.covVidBadge, "video");

  // Summary Scope
  if (dom.fusionScopeSummary) {
    dom.fusionScopeSummary.innerHTML = `
      Case ID: <font name="Courier">${escapeHtml(fusion.case_id)}</font><br/>
      <b>${fusion.evidence_count}</b> total evidence item(s) · <b>${fusion.analyzed_modalities_count}</b> analyzed modality/modalities.
    `;
  }

  // 1. Cross-Modal Entity Corroborations
  if (dom.fusionAssocCount) {
    dom.fusionAssocCount.textContent = `${assocs.length} match(es)`;
    dom.fusionAssocCount.style.display = assocs.length > 0 ? "inline-flex" : "none";
  }
  if (dom.fusionAssociationsContent) {
    if (assocs.length > 0) {
      dom.fusionAssociationsContent.innerHTML = assocs.map(a => `
        <div style="background: #1E293B; padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; border-left: 3px solid #3B82F6;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <span style="font-weight: 600; color: #60A5FA;">${escapeHtml(a.category.toUpperCase())}</span>
            <span class="badge badge--cobalt badge--xs mono">${escapeHtml(a.modalities_involved.join(" + "))}</span>
          </div>
          <p style="font-size: 12px; color: #E2E8F0; margin-bottom: 4px;">${escapeHtml(a.description)}</p>
          <p class="form-hint" style="font-size: 10px; color: #94A3B8;">${escapeHtml(a.forensic_qualification)}</p>
        </div>
      `).join("");
    } else {
      dom.fusionAssociationsContent.innerHTML = `<p class="muted">No cross-modal entity overlaps detected between modalities.</p>`;
    }
  }

  // 2. Temporal Audio-Video Alignments
  if (dom.fusionTemporalCount) {
    dom.fusionTemporalCount.textContent = `${tempAssocs.length} alignment(s)`;
    dom.fusionTemporalCount.style.display = tempAssocs.length > 0 ? "inline-flex" : "none";
  }
  if (dom.fusionTemporalContent) {
    if (tempAssocs.length > 0) {
      dom.fusionTemporalContent.innerHTML = tempAssocs.map(ta => `
        <div style="background: #1E293B; padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; border-left: 3px solid #10B981;">
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
            <span class="mono badge badge--emerald badge--xs">[${ta.audio_timestamp_range[0].toFixed(2)}s - ${ta.audio_timestamp_range[1].toFixed(2)}s]</span>
            <span style="font-size: 11px; color: #94A3B8;">Audio: ${escapeHtml(ta.audio_evidence_id)} ↔ Video: ${escapeHtml(ta.video_evidence_id)}</span>
          </div>
          <p style="font-size: 12px; color: #E2E8F0; margin-bottom: 4px;"><b>Speech:</b> "${escapeHtml(ta.speech_excerpt)}"</p>
          <p style="font-size: 12px; color: #CBD5E1; margin-bottom: 4px;"><b>Correlated Video Objects:</b> ${escapeHtml(ta.correlated_video_objects.join(", ") || "None")}</p>
          <p class="form-hint" style="font-size: 10px; color: #94A3B8;">${escapeHtml(ta.forensic_qualification)}</p>
        </div>
      `).join("");
    } else {
      dom.fusionTemporalContent.innerHTML = `<p class="muted">No concurrent speech and video detections established.</p>`;
    }
  }

  // 3. Contradictions & Inconsistencies
  if (dom.fusionConflictCount) {
    dom.fusionConflictCount.textContent = `${conflicts.length} flagged`;
    dom.fusionConflictCount.style.display = conflicts.length > 0 ? "inline-flex" : "none";
  }
  if (dom.fusionContradictionsContent) {
    if (conflicts.length > 0) {
      dom.fusionContradictionsContent.innerHTML = conflicts.map(cf => `
        <div style="background: #1E293B; padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; border-left: 3px solid #EF4444;">
          <div style="font-size: 12px; font-weight: 600; color: #F87171; margin-bottom: 4px;">
            ⚠ ${escapeHtml(cf.contradiction_type.replace(/_/g, " ").toUpperCase())}: "${escapeHtml(cf.term_a)}" vs "${escapeHtml(cf.term_b)}"
          </div>
          <p style="font-size: 12px; color: #E2E8F0; margin-bottom: 4px;">${escapeHtml(cf.explanation)}</p>
          <p class="form-hint" style="font-size: 10px; color: #FCA5A5;">${escapeHtml(cf.action_required)}</p>
        </div>
      `).join("");
    } else {
      dom.fusionContradictionsContent.innerHTML = `<p class="muted" style="color: #10B981;">No environmental scene descriptor contradictions flagged across evidence.</p>`;
    }
  }

  // 4. Unresolved Questions & Gaps
  if (dom.fusionQuestionsContent) {
    if (questions.length > 0) {
      dom.fusionQuestionsContent.innerHTML = questions.map(q => `
        <div style="padding: 4px 8px; border-bottom: 1px solid #334155; font-size: 12px; color: #CBD5E1;">
          • ${escapeHtml(q)}
        </div>
      `).join("");
    } else {
      dom.fusionQuestionsContent.innerHTML = `<p class="muted">All available modalities are analyzed and accounted for.</p>`;
    }
  }
}

async function runFusionAnalysis() {
  if (!state.activeCaseId) {
    showToast("Please select a case first to run multimodal fusion.", "warning");
    return;
  }

  if (dom.btnRunFusion) {
    dom.btnRunFusion.disabled = true;
    dom.btnRunFusion.innerHTML = `<span class="spin-loader">↻</span> Synthesizing…`;
  }
  if (dom.fusionStatusBadge) {
    dom.fusionStatusBadge.textContent = "Synthesizing cross-modal evidence…";
    dom.fusionStatusBadge.className = "panel-notice badge badge--amber";
  }

  showToast("Synthesizing multimodal forensic evidence fusion…", "info");

  const { ok, status, data } = await apiFetch(API.analyzeFusion(state.activeCaseId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

  if (dom.btnRunFusion) {
    dom.btnRunFusion.disabled = false;
    dom.btnRunFusion.innerHTML = `🔗 Synthesize Multimodal Fusion`;
  }

  if (!ok) {
    const errMsg = data.error || "Multimodal fusion failed.";
    showToast(errMsg, "error");
    if (dom.fusionStatusBadge) {
      dom.fusionStatusBadge.textContent = "Fusion Failed";
      dom.fusionStatusBadge.className = "panel-notice badge badge--crimson";
    }
    return;
  }

  renderFusionFindings(data.fusion);
  showToast("Multimodal evidence fusion synthesized successfully.", "success");
}

function getImageRenderGeometry(img) {
  if (!img || !img.complete || !img.naturalWidth || !img.naturalHeight) {
    return null;
  }
  const naturalW = img.naturalWidth;
  const naturalH = img.naturalHeight;
  const rect = img.getBoundingClientRect();
  const elemW = rect.width;
  const elemH = rect.height;
  if (elemW <= 0 || elemH <= 0) return null;

  const imgAspect = naturalW / naturalH;
  const elemAspect = elemW / elemH;
  let renderW, renderH, offsetX, offsetY;

  if (elemAspect > imgAspect) {
    renderH = elemH;
    renderW = elemH * imgAspect;
    offsetX = (elemW - renderW) / 2;
    offsetY = 0;
  } else {
    renderW = elemW;
    renderH = elemW / imgAspect;
    offsetX = 0;
    offsetY = (elemH - renderH) / 2;
  }

  return { naturalW, naturalH, elemW, elemH, renderW, renderH, offsetX, offsetY };
}

function extractNormalizedBox(obj, geom) {
  if (!obj) return null;
  if (Array.isArray(obj.box_normalized) && obj.box_normalized.length === 4) {
    let [c1, c2, c3, c4] = obj.box_normalized.map(Number);
    let x1 = Math.min(c1, c3);
    let y1 = Math.min(c2, c4);
    let x2 = Math.max(c1, c3);
    let y2 = Math.max(c2, c4);
    return {
      x1: Math.max(0, Math.min(1, x1)),
      y1: Math.max(0, Math.min(1, y1)),
      x2: Math.max(0, Math.min(1, x2)),
      y2: Math.max(0, Math.min(1, y2)),
    };
  }
  if (Array.isArray(obj.box_pixels) && obj.box_pixels.length === 4 && geom.naturalW && geom.naturalH) {
    let [px1, py1, px2, py2] = obj.box_pixels.map(Number);
    let x1 = Math.min(px1, px2) / geom.naturalW;
    let y1 = Math.min(py1, py2) / geom.naturalH;
    let x2 = Math.max(px1, px2) / geom.naturalW;
    let y2 = Math.max(py1, py2) / geom.naturalH;
    return {
      x1: Math.max(0, Math.min(1, x1)),
      y1: Math.max(0, Math.min(1, y1)),
      x2: Math.max(0, Math.min(1, x2)),
      y2: Math.max(0, Math.min(1, y2)),
    };
  }
  return null;
}

function drawBoundingBoxes(analysis) {
  const img = dom.evidenceImage;
  const canvas = dom.bboxCanvas;
  if (!img || !canvas) return;

  const geom = getImageRenderGeometry(img);
  if (!geom) {
    if (!img.complete) {
      img.onload = () => drawBoundingBoxes(analysis);
    }
    return;
  }

  const dpr = window.devicePixelRatio || 1;
  const displayW = Math.round(geom.elemW);
  const displayH = Math.round(geom.elemH);

  canvas.width = Math.round(displayW * dpr);
  canvas.height = Math.round(displayH * dpr);
  canvas.style.width = displayW + "px";
  canvas.style.height = displayH + "px";
  canvas.style.display = "block";

  const ctx = canvas.getContext("2d");
  ctx.resetTransform();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, displayW, displayH);

  const objects = (analysis.detection && analysis.detection.objects) || [];
  if (objects.length === 0) return;

  const minX = geom.offsetX;
  const maxX = geom.offsetX + geom.renderW;
  const minY = geom.offsetY;
  const maxY = geom.offsetY + geom.renderH;

  objects.forEach((obj) => {
    const norm = extractNormalizedBox(obj, geom);
    if (!norm) return;

    let boxX = geom.offsetX + norm.x1 * geom.renderW;
    let boxY = geom.offsetY + norm.y1 * geom.renderH;
    let boxW = (norm.x2 - norm.x1) * geom.renderW;
    let boxH = (norm.y2 - norm.y1) * geom.renderH;

    boxX = Math.max(minX, Math.min(maxX, boxX));
    boxY = Math.max(minY, Math.min(maxY, boxY));
    boxW = Math.max(0, Math.min(maxX - boxX, boxW));
    boxH = Math.max(0, Math.min(maxY - boxY, boxH));

    if (boxW <= 0 || boxH <= 0) return;

    // Draw box
    ctx.strokeStyle = "#38BDF8";
    ctx.lineWidth = 2;
    ctx.strokeRect(boxX, boxY, boxW, boxH);

    // Label
    const confPct = Math.round((obj.confidence || 0) * 100);
    const labelText = `${obj.label || "object"} ${confPct}%`;
    ctx.font = "bold 11px 'JetBrains Mono', monospace";
    const textWidth = ctx.measureText(labelText).width;
    const labelWidth = Math.min(textWidth + 8, maxX - minX);
    const labelHeight = 18;

    let labelY = boxY - labelHeight;
    if (labelY < minY) {
      labelY = boxY;
    }
    let labelX = Math.max(minX, Math.min(maxX - labelWidth, boxX));

    ctx.fillStyle = "rgba(11, 15, 23, 0.85)";
    ctx.fillRect(labelX, labelY, labelWidth, labelHeight);

    ctx.fillStyle = "#38BDF8";
    ctx.textBaseline = "middle";
    ctx.fillText(labelText, labelX + 4, labelY + labelHeight / 2);
  });
}

function renderImageFindings(analysis) {
  if (!analysis) return;

  // 1. RT-DETR Detections
  const det = analysis.detection || {};
  if (det.status === "success") {
    const objs = det.objects || [];
    dom.rtdetrCountBadge.textContent = `${objs.length} detected`;
    dom.rtdetrCountBadge.style.display = "inline-flex";

    if (objs.length === 0) {
      dom.rtdetrContent.innerHTML = `<p class="finding-block__body muted">No objects detected above threshold (${det.model || 'RT-DETR'}).</p>`;
    } else {
      let rows = objs.map(o => `
        <tr>
          <td><strong>${escapeHtml(o.label)}</strong></td>
          <td class="mono">${(o.confidence * 100).toFixed(1)}%</td>
          <td class="mono muted">[${o.box_pixels.join(', ')}]</td>
        </tr>
      `).join("");

      dom.rtdetrContent.innerHTML = `
        <table class="detections-table">
          <thead>
            <tr><th>Class</th><th>Conf</th><th>Bounding Box</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }
  } else if (det.status === "failed" || det.status === "unavailable") {
    dom.rtdetrCountBadge.style.display = "none";
    dom.rtdetrContent.innerHTML = `<p class="finding-block__body status-msg--error">RT-DETR error: ${escapeHtml(det.error || 'Failed')}</p>`;
  }

  // 2. BLIP Caption
  const cap = analysis.caption || {};
  if (cap.status === "success" && cap.caption) {
    dom.blipContent.innerHTML = `
      <p class="forensic-caption-quote">"${escapeHtml(cap.caption)}"</p>
      <p class="muted mono" style="font-size: 10px; margin-top: 4px;">Model: ${escapeHtml(cap.model || 'BLIP')}</p>
    `;
  } else if (cap.status === "failed" || cap.status === "unavailable") {
    dom.blipContent.innerHTML = `<p class="finding-block__body status-msg--error">BLIP error: ${escapeHtml(cap.error || 'Failed')}</p>`;
  }

  // 3. CLIP Similarity
  const clip = analysis.clip || {};
  if (clip.status === "success" && clip.matches) {
    let matchHtml = clip.matches.slice(0, 5).map(m => `
      <div class="clip-match-item">
        <span style="font-weight: 500;">${escapeHtml(m.label)}</span>
        <div class="clip-match-bar-wrapper">
          <div class="clip-match-bar" style="width: ${(m.similarity_score * 100).toFixed(1)}%;"></div>
        </div>
        <span class="mono">${(m.similarity_score * 100).toFixed(1)}%</span>
      </div>
    `).join("");

    dom.clipContent.innerHTML = `
      <div>${matchHtml}</div>
      <p class="form-hint" style="margin-top: 6px; font-size: 10px;">${escapeHtml(clip.forensic_notice || '')}</p>
    `;
  } else if (clip.status === "failed" || clip.status === "unavailable") {
    dom.clipContent.innerHTML = `<p class="finding-block__body status-msg--error">CLIP error: ${escapeHtml(clip.error || 'Failed')}</p>`;
  }

  const st = analysis.status || "completed";
  dom.imageStatusBadge.textContent = st === "partial" ? "Analysis Partial" : (st === "failed" ? "Analysis Failed" : "Analysis Complete");
  dom.imageStatusBadge.className = st === "partial" ? "panel-notice badge badge--amber" : (st === "failed" ? "panel-notice badge badge--crimson" : "panel-notice badge badge--emerald");
}

async function runImageAnalysis() {
  if (!state.activeCaseId || !state.activeEvidenceId) {
    showToast("Please select an image evidence item first.", "warning");
    return;
  }

  const ev = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
  if (!ev || ev.modality !== "image") {
    showToast("Selected item is not an image.", "warning");
    return;
  }

  dom.btnRunImageAnalysis.disabled = true;
  dom.btnRunImageAnalysis.innerHTML = `<span class="spin-loader">↻</span> Analyzing…`;
  dom.imageStatusBadge.textContent = "Running RT-DETR + CLIP + BLIP…";
  dom.imageStatusBadge.className = "panel-notice badge badge--amber";

  showToast("Starting sequential image analysis (RT-DETR, CLIP, BLIP)…", "info");

  const { ok, status, data } = await apiFetch(API.analyzeImage(state.activeCaseId, state.activeEvidenceId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

  dom.btnRunImageAnalysis.disabled = false;
  dom.btnRunImageAnalysis.innerHTML = `⚡ Run Image Analysis`;

  if (!ok) {
    const errMsg = data.error || "Analysis failed.";
    showToast(errMsg, "error");
    clearCanvas();
    resetImageFindings();
    dom.imageStatusBadge.textContent = "Analysis Failed";
    dom.imageStatusBadge.className = "panel-notice badge badge--crimson";
    return;
  }

  const analysis = data.analysis;
  ev.analysis_json = analysis;
  ev.analysis_status = data.status || "completed";

  renderImageFindings(analysis);
  drawBoundingBoxes(analysis);

  showToast("Image analysis completed successfully.", "success");
}

/* ══════════════════════════════════════════════════════════════════════════
   EVIDENCE UPLOAD
════════════════════════════════════════════════════════════════════════════ */
async function uploadFile(file) {
  if (!state.activeCaseId) {
    showToast("Select or create a case before uploading.", "warning");
    return;
  }

  const setStatus = (msg, cls = "") => {
    dom.uploadStatus.textContent = msg;
    dom.uploadStatus.className = `form-hint status-msg ${cls}`;
  };

  setStatus(`Uploading ${file.name}…`);

  const formData = new FormData();
  formData.append("file", file);

  const { ok, data } = await apiFetch(API.evidence(state.activeCaseId), {
    method: "POST",
    body: formData,
  });

  if (!ok) {
    const msg = data.error || "Upload failed.";
    setStatus(msg, "status-msg--error");
    showToast(msg, "error");
    return;
  }

  const ev = data.evidence;
  setStatus(
    `✓ Uploaded ${ev.original_name} (${formatBytes(ev.file_size)}) · SHA-256: ${ev.sha256.slice(0, 16)}…`,
    "status-msg--ok"
  );
  showToast(`Evidence "${ev.original_name}" uploaded successfully.`, "success");

  await loadEvidence(state.activeCaseId);
}

/* ══════════════════════════════════════════════════════════════════════════
   TAB SWITCHING
════════════════════════════════════════════════════════════════════════════ */
const PANEL_MAP = {
  image:   dom.panelImage,
  audio:   dom.panelAudio,
  video:   dom.panelVideo,
  fusion:  dom.panelFusion,
  scene3d: dom.panelScene3d,
};

function activateTab(tabId) {
  dom.tabBtns.forEach((btn) => {
    const active = btn.dataset.tab === tabId;
    btn.classList.toggle("tab-btn--active", active);
    btn.setAttribute("aria-selected", active);
  });

  if (tabId === "fusion" || tabId === "scene3d") {
    showTabPanels();
  }

  Object.entries(PANEL_MAP).forEach(([id, panel]) => {
    if (panel) {
      panel.style.display = id === tabId ? "flex" : "none";
    }
  });

  if (tabId === "scene3d") {
    onScene3dTabActivated();
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   VIEWPORT STATE
════════════════════════════════════════════════════════════════════════════ */
function showEmptyState() {
  dom.emptyState.style.display = "flex";
  dom.tabPanels.style.display = "none";
}

function showTabPanels() {
  dom.emptyState.style.display = "none";
  dom.tabPanels.style.display = "flex";
}

/* ══════════════════════════════════════════════════════════════════════════
   DRAG & DROP
════════════════════════════════════════════════════════════════════════════ */
function initDragDrop() {
  const zone = dom.uploadZone;

  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("upload-zone--dragover");
  });

  zone.addEventListener("dragleave", () => {
    zone.classList.remove("upload-zone--dragover");
  });

  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("upload-zone--dragover");
    const file = e.dataTransfer?.files?.[0];
    if (file) uploadFile(file);
  });

  dom.fileInput.addEventListener("change", () => {
    const file = dom.fileInput.files?.[0];
    if (file) {
      uploadFile(file);
      dom.fileInput.value = ""; // reset so same file can be re-uploaded
    }
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   PHASE 7 FORENSIC AI INVESTIGATION CHAT ASSISTANT
════════════════════════════════════════════════════════════════════════════ */
function resetChatAssistant() {
  if (dom.chatInput) {
    dom.chatInput.disabled = true;
    dom.chatInput.placeholder = "Select an active case to ask questions…";
    dom.chatInput.value = "";
  }
  if (dom.btnChatSend) dom.btnChatSend.disabled = true;
  if (dom.btnClearChat) dom.btnClearChat.disabled = true;
  if (dom.chatStatusBadge) {
    dom.chatStatusBadge.textContent = "Standby";
    dom.chatStatusBadge.className = "badge badge--xs badge--emerald";
  }
  if (dom.chatSuggestions) {
    dom.chatSuggestions.querySelectorAll(".chip-btn").forEach(btn => btn.disabled = true);
  }
  if (dom.chatMessages) {
    dom.chatMessages.innerHTML = `<p class="muted chat-hint" id="chat-empty-hint">Select an active case to ask questions about its evidence. All answers are strictly grounded in verified forensic data.</p>`;
  }
}

function enableChatAssistant() {
  if (dom.chatInput) {
    dom.chatInput.disabled = false;
    dom.chatInput.placeholder = "Ask about this case's evidence…";
  }
  if (dom.btnChatSend) dom.btnChatSend.disabled = false;
  if (dom.btnClearChat) dom.btnClearChat.disabled = false;
  if (dom.chatStatusBadge) {
    dom.chatStatusBadge.textContent = "Ready";
    dom.chatStatusBadge.className = "badge badge--xs badge--emerald";
  }
  if (dom.chatSuggestions) {
    dom.chatSuggestions.querySelectorAll(".chip-btn").forEach(btn => btn.disabled = false);
  }
}

async function loadChatHistory(caseId) {
  if (!caseId) return;
  enableChatAssistant();
  const { ok, data } = await apiFetch(API.chatHistory(caseId));
  if (!ok) return;

  if (dom.chatMessages) {
    dom.chatMessages.innerHTML = "";
    const msgs = data.messages || [];
    if (msgs.length === 0) {
      dom.chatMessages.innerHTML = `<p class="muted chat-hint" id="chat-empty-hint">No messages yet. Ask a question below or pick a suggestion chip.</p>`;
    } else {
      msgs.forEach(msg => renderChatMessage(msg));
      dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
    }
  }
}

function formatForensicTextWithPills(text) {
  if (!text) return "";
  let safe = escapeHtml(text);

  // Format [ev_xxx @ 12.5s] timestamp pills
  safe = safe.replace(/\[(ev_[a-zA-Z0-9_\-]+)\s*@\s*([0-9\.]+)s?\]/g, (match, eid, ts) => {
    return `<a class="citation-pill citation-pill--timestamp" href="#" data-eid="${eid}" data-ts="${ts}">⏱️ ${eid} @ ${parseFloat(ts).toFixed(1)}s</a>`;
  });

  // Format general [ev_xxx] evidence pills
  safe = safe.replace(/\[(ev_[a-zA-Z0-9_\-]+)\]/g, (match, eid) => {
    return `<a class="citation-pill" href="#" data-eid="${eid}">📁 ${eid}</a>`;
  });

  // Convert double/single newlines to breaks
  return safe.replace(/\n\n+/g, "<br /><br />").replace(/\n/g, "<br />");
}

function renderChatMessage(msg) {
  if (!dom.chatMessages) return;
  const bubble = document.createElement("div");
  const isUser = msg.role === "user";
  bubble.className = `chat-bubble ${isUser ? "chat-bubble--user" : "chat-bubble--assistant"}`;

  const timeStr = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

  if (isUser) {
    bubble.innerHTML = `
      <div>${escapeHtml(msg.content)}</div>
      <div class="chat-bubble__meta"><span>Investigator</span><span>${timeStr}</span></div>
    `;
  } else {
    const meta = msg.metadata || {};
    const answerHtml = formatForensicTextWithPills(msg.content || meta.answer || "");
    
    let insufficientBanner = "";
    if (meta.insufficient_evidence) {
      insufficientBanner = `<div class="chat-insufficient-banner">⚠️ Note: Evidence is insufficient to conclusively answer this query.</div>`;
    }

    let supportingHtml = "";
    const supporting = meta.supporting_evidence || [];
    if (supporting.length > 0) {
      supportingHtml = `
        <div class="chat-supporting-list">
          <span style="font-size:10px; color:var(--color-text-muted); font-weight:600; text-transform:uppercase;">Cited Observations:</span>
          ${supporting.map(s => {
            const eid = escapeHtml(s.evidence_id || "");
            const ts = s.timestamp_seconds != null ? `${parseFloat(s.timestamp_seconds).toFixed(1)}s` : null;
            const pill = ts
              ? `<a class="citation-pill citation-pill--timestamp" href="#" data-eid="${eid}" data-ts="${s.timestamp_seconds}">⏱️ ${eid} @ ${ts}</a>`
              : `<a class="citation-pill" href="#" data-eid="${eid}">📁 ${eid}</a>`;
            const confStr = s.confidence != null ? ` <span class="badge badge--xs badge--cobalt">${(s.confidence * 100).toFixed(0)}%</span>` : "";
            return `<div class="chat-supporting-item">${pill} <span>${escapeHtml(s.observation || "")}</span>${confStr}</div>`;
          }).join("")}
        </div>
      `;
    }

    let limitationsHtml = "";
    const limitations = meta.limitations || [];
    if (limitations.length > 0) {
      limitationsHtml = `
        <div class="chat-limitations-box">
          <strong>Forensic Caveats:</strong>
          <ul style="margin:2px 0 0 14px; padding:0;">
            ${limitations.map(l => `<li>${escapeHtml(l)}</li>`).join("")}
          </ul>
        </div>
      `;
    }

    bubble.innerHTML = `
      ${insufficientBanner}
      <div>${answerHtml}</div>
      ${supportingHtml}
      ${limitationsHtml}
      <div class="chat-bubble__meta"><span>CrimeVision AI</span><span>${timeStr}</span></div>
    `;
  }

  // Attach click events for any citation pills in this message
  bubble.querySelectorAll(".citation-pill").forEach(pill => {
    pill.addEventListener("click", (e) => {
      e.preventDefault();
      const eid = pill.dataset.eid;
      const ts = pill.dataset.ts ? parseFloat(pill.dataset.ts) : null;
      handleCitationClick(eid, ts);
    });
  });

  dom.chatMessages.appendChild(bubble);
  dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
}

function handleCitationClick(evidenceId, timestamp) {
  if (!evidenceId) return;
  const ev = state.evidence.find(e => e.evidence_id === evidenceId);
  if (!ev) {
    showToast(`Evidence ${evidenceId} not found in active case.`, "warning");
    return;
  }

  // Select evidence item
  selectEvidence(evidenceId);

  // If timestamp is specified and modality is video, seek video
  if (timestamp != null && ev.modality === "video") {
    activateTab("video");
    if (dom.evidenceVideo) {
      dom.evidenceVideo.currentTime = timestamp;
      dom.evidenceVideo.play().catch(() => {});
      showToast(`Navigated to ${ev.filename} at ${timestamp.toFixed(1)}s`, "info");
    }
  } else {
    activateTab(ev.modality);
    showToast(`Inspecting evidence ${ev.original_name || ev.filename}`, "info");
  }
}

async function sendChatMessage(query) {
  const caseId = state.activeCaseId;
  if (!caseId) {
    showToast("Please select an active case first.", "warning");
    return;
  }
  const cleanQuery = (query || (dom.chatInput ? dom.chatInput.value : "")).trim();
  if (!cleanQuery) return;

  // Clear input
  if (dom.chatInput) dom.chatInput.value = "";

  // Clear empty hint if present
  const hint = document.getElementById("chat-empty-hint");
  if (hint) hint.remove();

  // Render user message bubble immediately
  renderChatMessage({
    role: "user",
    content: cleanQuery,
    created_at: new Date().toISOString(),
  });

  // Disable input and show spinner
  if (dom.chatInput) dom.chatInput.disabled = true;
  if (dom.btnChatSend) dom.btnChatSend.disabled = true;
  if (dom.chatSendText) dom.chatSendText.style.display = "none";
  if (dom.chatSendSpinner) dom.chatSendSpinner.style.display = "inline-block";
  if (dom.chatStatusBadge) {
    dom.chatStatusBadge.textContent = "Analyzing…";
    dom.chatStatusBadge.className = "badge badge--xs badge--amber";
  }

  try {
    const { ok, data } = await apiFetch(API.chat(caseId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: cleanQuery }),
    });

    if (!ok) {
      if (data.api_key_missing) {
        renderChatMessage({
          role: "assistant",
          content: "⚠️ **Gemini API Key Required**\n\nTo activate the AI Forensic Assistant, please configure `GEMINI_API_KEY` in your `.env` file.\n\nGet an API key from Google AI Studio (https://aistudio.google.com/).",
          created_at: new Date().toISOString(),
        });
        showToast("Gemini API key is not configured.", "warning");
      } else {
        let errorMsg = data.error || "Server error";
        if (errorMsg === "Failed to fetch") {
          errorMsg = "Unable to connect to the backend server. Please verify your connection and server status.";
        }
        renderChatMessage({
          role: "assistant",
          content: `❌ Query failed: ${errorMsg}`,
          created_at: new Date().toISOString(),
        });
        showToast(errorMsg, "error");
      }
      return;
    }

    const responseObj = data.response || {};
    renderChatMessage({
      role: "assistant",
      content: responseObj.answer || "No response provided.",
      metadata: responseObj,
      created_at: data.created_at || new Date().toISOString(),
    });
  } catch (err) {
    renderChatMessage({
      role: "assistant",
      content: `❌ Network error while connecting to forensic AI service: ${err.message}`,
      created_at: new Date().toISOString(),
    });
    showToast("Network error connecting to chat service.", "error");
  } finally {
    if (dom.chatInput) {
      dom.chatInput.disabled = false;
      dom.chatInput.focus();
    }
    if (dom.btnChatSend) dom.btnChatSend.disabled = false;
    if (dom.chatSendText) dom.chatSendText.style.display = "inline";
    if (dom.chatSendSpinner) dom.chatSendSpinner.style.display = "none";
    if (dom.chatStatusBadge) {
      dom.chatStatusBadge.textContent = "Ready";
      dom.chatStatusBadge.className = "badge badge--xs badge--emerald";
    }
  }
}

async function clearChat() {
  const caseId = state.activeCaseId;
  if (!caseId) return;

  const { ok, data } = await apiFetch(API.chatHistory(caseId), {
    method: "DELETE",
  });

  if (ok) {
    if (dom.chatMessages) {
      dom.chatMessages.innerHTML = `<p class="muted chat-hint" id="chat-empty-hint">Chat history cleared. Ask a question below or pick a suggestion chip.</p>`;
    }
    showToast("Chat history cleared.", "info");
  } else {
    showToast(data.error || "Failed to clear chat history.", "error");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   PHASE 8 THREE.JS ESTIMATED 3D SPATIAL EVIDENCE VISUALIZATION
════════════════════════════════════════════════════════════════════════════ */

const scene3dState = {
  scene: null,
  camera: null,
  renderer: null,
  controls: null,
  objectsGroup: null,
  gridHelper: null,
  rawObjects: [],
  selectedObjectId: null,
  animationId: null,
  showGrid: true,
  showLabels: true,
  minConfidence: 0.30,
  isInitialized: false,
};

function initThreeJs() {
  if (scene3dState.isInitialized) return;
  if (typeof THREE === "undefined") {
    console.warn("Three.js is not loaded.");
    return;
  }

  const container = dom.scene3dViewport;
  const canvas = dom.threejsCanvas;
  if (!container || !canvas) return;

  const width = container.clientWidth || 800;
  const height = container.clientHeight || 520;

  // Scene with forensic dark tone
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x080C14);
  scene.fog = new THREE.FogExp2(0x080C14, 0.025);
  scene3dState.scene = scene;

  // Camera
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 500);
  camera.position.set(0, 14, 20);
  scene3dState.camera = camera;

  // Renderer
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  scene3dState.renderer = renderer;

  // OrbitControls
  if (typeof THREE.OrbitControls !== "undefined") {
    const controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 + 0.05;
    controls.minDistance = 3;
    controls.maxDistance = 60;
    controls.target.set(0, 0, 0);
    scene3dState.controls = controls;
  }

  // Lights
  const ambientLight = new THREE.AmbientLight(0xFFFFFF, 0.7);
  scene.add(ambientLight);

  const dirLight = new THREE.DirectionalLight(0xF8FAFC, 0.85);
  dirLight.position.set(12, 22, 14);
  scene.add(dirLight);

  const blueFill = new THREE.DirectionalLight(0x3B82F6, 0.3);
  blueFill.position.set(-12, 8, -12);
  scene.add(blueFill);

  // Calibrated ground grid
  const gridHelper = new THREE.GridHelper(24, 24, 0x3B82F6, 0x1E293B);
  gridHelper.position.y = 0.0;
  scene.add(gridHelper);
  scene3dState.gridHelper = gridHelper;

  // Subtle coordinate axes
  const axes = new THREE.AxesHelper(1.5);
  axes.position.set(0, 0.01, 0);
  scene.add(axes);

  // Group for detection proxies
  const objectsGroup = new THREE.Group();
  scene.add(objectsGroup);
  scene3dState.objectsGroup = objectsGroup;

  // Raycaster for object selection on click
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();

  canvas.addEventListener("click", (event) => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(objectsGroup.children, true);

    if (intersects.length > 0) {
      let target = intersects[0].object;
      while (target && (!target.userData || !target.userData.objectData) && target.parent !== objectsGroup) {
        target = target.parent;
      }
      if (target && target.userData && target.userData.objectData) {
        selectSceneObject(target.userData.objectData);
      }
    }
  });

  // Animation Loop
  function animate() {
    scene3dState.animationId = requestAnimationFrame(animate);
    if (scene3dState.controls) {
      scene3dState.controls.update();
    }

    // Subtle beacon animation for weapons
    const time = Date.now() * 0.003;
    objectsGroup.children.forEach(group => {
      if (group.userData && group.userData.isWeapon && group.userData.beacon) {
        const s = 1.0 + Math.sin(time) * 0.15;
        group.userData.beacon.scale.set(s, s, s);
      }
      if (group.userData && group.userData.sprite) {
        group.userData.sprite.visible = scene3dState.showLabels && group.visible;
      }
    });

    renderer.render(scene, camera);
  }
  animate();

  window.addEventListener("resize", onScene3dResize);
  scene3dState.isInitialized = true;
}

function onScene3dResize() {
  if (!scene3dState.renderer || !scene3dState.camera || !dom.scene3dViewport) return;
  const w = dom.scene3dViewport.clientWidth || 800;
  const h = dom.scene3dViewport.clientHeight || 520;
  scene3dState.camera.aspect = w / h;
  scene3dState.camera.updateProjectionMatrix();
  scene3dState.renderer.setSize(w, h);
}

function createTextSprite(text, bgColor = "#1E293B", textColor = "#F8FAFC") {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = bgColor;
  ctx.beginPath();
  ctx.roundRect(4, 4, 248, 56, 12);
  ctx.fill();

  ctx.strokeStyle = "rgba(255,255,255,0.3)";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = textColor;
  ctx.font = "bold 22px 'JetBrains Mono', monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 128, 32);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const spriteMaterial = new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true });
  const sprite = new THREE.Sprite(spriteMaterial);
  sprite.scale.set(1.8, 0.45, 1);
  return sprite;
}

function createProceduralProxy(obj) {
  const group = new THREE.Group();
  const label = (obj.label || "object").toLowerCase();
  const color = new THREE.Color(obj.color_hex || "#94A3B8");
  const material = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.35,
    metalness: 0.25,
  });

  const pWidth = obj.proxy_dimensions?.width || 0.8;
  const pHeight = obj.proxy_dimensions?.height || 1.6;
  const pDepth = obj.proxy_dimensions?.depth || 0.8;

  let mainMesh = null;
  let isWeapon = false;
  let beacon = null;

  if (label === "person" || label === "pedestrian") {
    // Capsule proxy: cylinder body + sphere head
    const bodyGeo = new THREE.CylinderGeometry(0.28, 0.34, pHeight * 0.75, 16);
    const body = new THREE.Mesh(bodyGeo, material);
    body.position.y = (pHeight * 0.75) / 2;

    const headGeo = new THREE.SphereGeometry(0.24, 16, 12);
    const head = new THREE.Mesh(headGeo, material);
    head.position.y = pHeight * 0.75 + 0.24;

    group.add(body);
    group.add(head);
    mainMesh = body;
  } else if (label.includes("car") || label.includes("truck") || label.includes("bus") || label.includes("vehicle")) {
    // Vehicle proxy: chassis + cabin
    const chassisGeo = new THREE.BoxGeometry(pWidth * 1.4, pHeight * 0.45, pDepth * 1.5);
    const chassis = new THREE.Mesh(chassisGeo, material);
    chassis.position.y = (pHeight * 0.45) / 2;

    const cabinGeo = new THREE.BoxGeometry(pWidth * 1.0, pHeight * 0.4, pDepth * 0.9);
    const cabin = new THREE.Mesh(cabinGeo, new THREE.MeshStandardMaterial({
      color: color.clone().offsetHSL(0, 0, 0.1),
      roughness: 0.2,
      metalness: 0.5,
    }));
    cabin.position.y = (pHeight * 0.45) + (pHeight * 0.4) / 2;

    group.add(chassis);
    group.add(cabin);
    mainMesh = chassis;
  } else if (label.includes("knife") || label.includes("weapon") || label.includes("gun") || label.includes("pistol") || label.includes("scissors")) {
    isWeapon = true;
    const bladeGeo = new THREE.ConeGeometry(0.2, pHeight * 0.8, 6);
    const blade = new THREE.Mesh(bladeGeo, material);
    blade.position.y = (pHeight * 0.8) / 2;
    blade.rotation.z = Math.PI / 4;

    const ringGeo = new THREE.TorusGeometry(0.4, 0.05, 8, 24);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0xEF4444, wireframe: true });
    beacon = new THREE.Mesh(ringGeo, ringMat);
    beacon.rotation.x = Math.PI / 2;
    beacon.position.y = (pHeight * 0.8) / 2;

    group.add(blade);
    group.add(beacon);
    mainMesh = blade;
  } else {
    const boxGeo = new THREE.BoxGeometry(pWidth, pHeight * 0.6, pDepth);
    const box = new THREE.Mesh(boxGeo, material);
    box.position.y = (pHeight * 0.6) / 2;
    group.add(box);
    mainMesh = box;
  }

  // Ground drop-line
  const lineMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 });
  const linePoints = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, obj.spatial_coords.y, 0)];
  const lineGeo = new THREE.BufferGeometry().setFromPoints(linePoints);
  const dropLine = new THREE.Line(lineGeo, lineMat);
  group.add(dropLine);

  // Ground marker ring
  const ringGeo = new THREE.RingGeometry(0.15, 0.4, 16);
  const ringMat = new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, transparent: true, opacity: 0.6 });
  const groundRing = new THREE.Mesh(ringGeo, ringMat);
  groundRing.rotation.x = Math.PI / 2;
  groundRing.position.y = 0.01;
  group.add(groundRing);

  // Floating Label Sprite
  const confPct = `${(obj.confidence * 100).toFixed(0)}%`;
  const sprite = createTextSprite(`${obj.label} ${confPct}`, "#111827", obj.color_hex);
  sprite.position.y = obj.spatial_coords.y + (pHeight * 0.8) + 0.4;
  group.add(sprite);

  group.position.set(obj.spatial_coords.x, 0, obj.spatial_coords.z);

  group.userData = {
    objectData: obj,
    mainMesh,
    isWeapon,
    beacon,
    dropLine,
    groundRing,
    sprite,
  };
  group.traverse(child => {
    if (child.isMesh) {
      child.userData = group.userData;
    }
  });

  return group;
}

async function onScene3dTabActivated() {
  initThreeJs();
  onScene3dResize();

  const caseId = state.activeCaseId;
  if (!caseId) {
    if (dom.scene3dEmptyState) {
      dom.scene3dEmptyState.style.display = "flex";
      dom.scene3dEmptyText.innerHTML = "No active case selected.<br />Select or create a case to visualize 3D evidence.";
    }
    return;
  }

  await loadScene3d(caseId);
}

async function loadScene3d(caseId) {
  if (!caseId) return;

  if (dom.scene3dLoading) dom.scene3dLoading.style.display = "flex";
  if (dom.scene3dEmptyState) dom.scene3dEmptyState.style.display = "none";
  if (dom.scene3dDetailsCard) dom.scene3dDetailsCard.style.display = "none";

  try {
    const { ok, data } = await apiFetch(API.spatialVisualization(caseId));
    if (!ok) {
      if (dom.scene3dEmptyState) {
        dom.scene3dEmptyState.style.display = "flex";
        dom.scene3dEmptyText.textContent = data.error || "Failed to load 3D spatial data.";
      }
      return;
    }

    renderSceneObjects(data);
  } catch (err) {
    if (dom.scene3dEmptyState) {
      dom.scene3dEmptyState.style.display = "flex";
      dom.scene3dEmptyText.textContent = "Error loading 3D evidence scene: " + err.message;
    }
  } finally {
    if (dom.scene3dLoading) dom.scene3dLoading.style.display = "none";
  }
}

function renderSceneObjects(data) {
  initThreeJs();
  const group = scene3dState.objectsGroup;
  if (!group) return;

  while (group.children.length > 0) {
    const child = group.children[0];
    group.remove(child);
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      if (Array.isArray(child.material)) child.material.forEach(m => m.dispose());
      else child.material.dispose();
    }
  }

  const rawObjs = data.objects || [];
  scene3dState.rawObjects = rawObjs;

  if (rawObjs.length === 0) {
    if (dom.scene3dEmptyState) {
      dom.scene3dEmptyState.style.display = "flex";
      dom.scene3dEmptyText.innerHTML = "No analyzed image or video detections found in this case.<br />Analyze image or video evidence first to populate 3D spatial markers.";
    }
    if (dom.scene3dLegend) dom.scene3dLegend.style.display = "none";
    if (dom.scene3dCountBadge) dom.scene3dCountBadge.textContent = "0 objects";
    return;
  }

  if (dom.scene3dEmptyState) dom.scene3dEmptyState.style.display = "none";

  rawObjs.forEach(obj => {
    const proxyGroup = createProceduralProxy(obj);
    group.add(proxyGroup);
  });

  // Populate Categories Filter
  if (dom.scene3dFilterCategory) {
    const prevCat = dom.scene3dFilterCategory.value;
    dom.scene3dFilterCategory.innerHTML = `<option value="">All Categories (${rawObjs.length})</option>`;
    const cats = data.summary?.categories || [];
    cats.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      dom.scene3dFilterCategory.appendChild(opt);
    });
    if (cats.includes(prevCat)) dom.scene3dFilterCategory.value = prevCat;
  }

  // Populate Evidence Filter
  if (dom.scene3dFilterEvidence) {
    const prevEv = dom.scene3dFilterEvidence.value;
    dom.scene3dFilterEvidence.innerHTML = `<option value="">All Evidence (${rawObjs.length})</option>`;
    const sources = data.summary?.evidence_sources || [];
    sources.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.evidence_id;
      opt.textContent = `${s.filename} (${s.object_count})`;
      dom.scene3dFilterEvidence.appendChild(opt);
    });
    if (sources.find(s => s.evidence_id === prevEv)) dom.scene3dFilterEvidence.value = prevEv;
  }

  // Render Legend
  if (dom.scene3dLegend && dom.scene3dLegendList) {
    const legend = data.legend || [];
    if (legend.length > 0) {
      dom.scene3dLegendList.innerHTML = legend.map(item => `
        <div class="scene3d-legend-item">
          <span class="scene3d-legend-dot" style="background-color:${item.color_hex};"></span>
          <span>${escapeHtml(item.category)}</span>
        </div>
      `).join("");
      dom.scene3dLegend.style.display = "block";
    } else {
      dom.scene3dLegend.style.display = "none";
    }
  }

  filterSceneObjects();
}

function filterSceneObjects() {
  const group = scene3dState.objectsGroup;
  if (!group) return;

  const cat = (dom.scene3dFilterCategory ? dom.scene3dFilterCategory.value : "").toLowerCase();
  const eid = dom.scene3dFilterEvidence ? dom.scene3dFilterEvidence.value : "";
  const minConf = dom.scene3dConfSlider ? (parseInt(dom.scene3dConfSlider.value, 10) / 100) : 0.30;

  let visibleCount = 0;
  const totalCount = group.children.length;

  group.children.forEach(child => {
    const data = child.userData?.objectData;
    if (!data) return;

    const matchCat = !cat || (data.label && data.label.toLowerCase() === cat);
    const matchEid = !eid || data.evidence_id === eid;
    const matchConf = (data.confidence || 0) >= minConf;

    const visible = matchCat && matchEid && matchConf;
    child.visible = visible;
    if (visible) visibleCount++;
  });

  if (dom.scene3dCountBadge) {
    dom.scene3dCountBadge.textContent = `${visibleCount} / ${totalCount} objects`;
  }
}

function selectSceneObject(objData) {
  if (!objData || !dom.scene3dDetailsCard) return;

  dom.detCardLabel.textContent = objData.label || "Object";
  dom.detCardLabel.style.backgroundColor = objData.color_hex || "var(--color-cobalt)";
  
  const confPct = `${((objData.confidence || 0) * 100).toFixed(0)}%`;
  dom.detCardConf.textContent = confPct;
  dom.detCardEvidence.textContent = `${objData.evidence_name || objData.evidence_id}`;

  if (objData.timestamp_seconds != null) {
    dom.detCardTimestampRow.style.display = "block";
    dom.detCardTimestamp.textContent = `${parseFloat(objData.timestamp_seconds).toFixed(1)}s (Frame ${objData.frame_index ?? "N/A"})`;
  } else {
    dom.detCardTimestampRow.style.display = "none";
  }

  const bbox = objData.box_pixels || objData.box_normalized || [];
  dom.detCardBbox.textContent = JSON.stringify(bbox);

  const pos = objData.spatial_coords || { x: 0, y: 0, z: 0 };
  dom.detCardPos.textContent = `(x:${pos.x}, y:${pos.y}, z:${pos.z})`;

  if (dom.btnDetCardNavigate) {
    dom.btnDetCardNavigate.onclick = () => {
      selectEvidence(objData.evidence_id);
      activateTab(objData.modality || "image");
      if (objData.modality === "video" && objData.timestamp_seconds != null && dom.evidenceVideo) {
        dom.evidenceVideo.currentTime = objData.timestamp_seconds;
        dom.evidenceVideo.play().catch(() => {});
        showToast(`Navigated to ${objData.evidence_name} @ ${objData.timestamp_seconds}s`, "info");
      } else {
        showToast(`Inspecting ${objData.evidence_name}`, "info");
      }
    };
  }

  dom.scene3dDetailsCard.style.display = "block";
}

function resetScene3d() {
  if (scene3dState.objectsGroup) {
    while (scene3dState.objectsGroup.children.length > 0) {
      scene3dState.objectsGroup.remove(scene3dState.objectsGroup.children[0]);
    }
  }
  scene3dState.rawObjects = [];
  if (dom.scene3dDetailsCard) dom.scene3dDetailsCard.style.display = "none";
  if (dom.scene3dLegend) dom.scene3dLegend.style.display = "none";
  if (dom.scene3dCountBadge) dom.scene3dCountBadge.textContent = "0 objects";
  if (dom.scene3dEmptyState) {
    dom.scene3dEmptyState.style.display = "flex";
    dom.scene3dEmptyText.innerHTML = "No analyzed image or video evidence in active case.<br />Analyze images or videos to project detections into the 3D scene.";
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   PHASE 10 CINEMATIC HERO 3D SCENE (Three.js WebGL)
════════════════════════════════════════════════════════════════════════════ */

const hero3dState = {
  scene: null,
  camera: null,
  renderer: null,
  coreGroup: null,
  particles: null,
  scanRing: null,
  animationId: null,
  isPaused: false,
  isInitialized: false,
  targetMouseX: 0,
  targetMouseY: 0,
  currentMouseX: 0,
  currentMouseY: 0,
};

function initHero3D() {
  if (hero3dState.isInitialized) return;
  if (typeof THREE === "undefined") {
    console.warn("Three.js not loaded for Hero 3D.");
    return;
  }

  const canvas = document.getElementById("hero-three-canvas");
  const heroSection = document.getElementById("hero");
  if (!canvas || !heroSection) return;

  const width = heroSection.clientWidth || window.innerWidth;
  const height = heroSection.clientHeight || window.innerHeight;

  // Scene
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x06080D, 0.02);
  hero3dState.scene = scene;

  // Camera
  const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
  camera.position.set(0, 2.5, 12);
  hero3dState.camera = camera;

  // Renderer
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: "high-performance",
  });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  hero3dState.renderer = renderer;

  // Volumetric Ground Grid
  const gridHelper = new THREE.GridHelper(40, 40, 0x00F0FF, 0x111c2e);
  gridHelper.position.y = -3.5;
  scene.add(gridHelper);

  // Group for Central Forensic Data Core
  const coreGroup = new THREE.Group();
  scene.add(coreGroup);
  hero3dState.coreGroup = coreGroup;

  // Outer wireframe icosahedron (Forensic Core Cage)
  const icosaGeo = new THREE.IcosahedronGeometry(2.0, 1);
  const icosaMat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    wireframe: true,
    transparent: true,
    opacity: 0.35,
  });
  const icosaMesh = new THREE.Mesh(icosaGeo, icosaMat);
  coreGroup.add(icosaMesh);

  // Inner solid core node
  const innerGeo = new THREE.OctahedronGeometry(1.0, 0);
  const innerMat = new THREE.MeshBasicMaterial({
    color: 0x3B82F6,
    wireframe: true,
    transparent: true,
    opacity: 0.6,
  });
  const innerMesh = new THREE.Mesh(innerGeo, innerMat);
  coreGroup.add(innerMesh);

  // Concentric Orbital Ring 1
  const ring1Geo = new THREE.TorusGeometry(3.2, 0.02, 16, 100);
  const ring1Mat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    transparent: true,
    opacity: 0.45,
  });
  const ring1 = new THREE.Mesh(ring1Geo, ring1Mat);
  ring1.rotation.x = Math.PI / 3;
  coreGroup.add(ring1);

  // Concentric Orbital Ring 2 (tilted differently)
  const ring2Geo = new THREE.TorusGeometry(3.8, 0.02, 16, 100);
  const ring2Mat = new THREE.MeshBasicMaterial({
    color: 0x6366F1,
    transparent: true,
    opacity: 0.3,
  });
  const ring2 = new THREE.Mesh(ring2Geo, ring2Mat);
  ring2.rotation.y = Math.PI / 4;
  ring2.rotation.x = -Math.PI / 6;
  coreGroup.add(ring2);

  // Radar / Scanning Pulse Ring
  const scanGeo = new THREE.RingGeometry(0.1, 4.5, 64);
  const scanMat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    transparent: true,
    opacity: 0.08,
    side: THREE.DoubleSide,
  });
  const scanRing = new THREE.Mesh(scanGeo, scanMat);
  scanRing.rotation.x = Math.PI / 2;
  scanRing.position.y = -3.45;
  scene.add(scanRing);
  hero3dState.scanRing = scanRing;

  // Particle Field: 700 Forensic Data Points
  const particleCount = 700;
  const particleGeo = new THREE.BufferGeometry();
  const particlePositions = new Float32Array(particleCount * 3);
  for (let i = 0; i < particleCount * 3; i += 3) {
    particlePositions[i] = (Math.random() - 0.5) * 35;
    particlePositions[i + 1] = (Math.random() - 0.5) * 20;
    particlePositions[i + 2] = (Math.random() - 0.5) * 25;
  }
  particleGeo.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
  const particleMat = new THREE.PointsMaterial({
    color: 0x38BDF8,
    size: 0.07,
    transparent: true,
    opacity: 0.65,
  });
  const particleSystem = new THREE.Points(particleGeo, particleMat);
  scene.add(particleSystem);
  hero3dState.particles = particleSystem;

  // Mouse move listener for smooth 3D tilt
  window.addEventListener("mousemove", (e) => {
    hero3dState.targetMouseX = (e.clientX / window.innerWidth) * 2 - 1;
    hero3dState.targetMouseY = -(e.clientY / window.innerHeight) * 2 + 1;
  });

  // Responsive resize
  window.addEventListener("resize", onHeroResize);

  // Visibility optimization: Pause render loop when #hero is off-screen
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          hero3dState.isPaused = !entry.isIntersecting;
          if (entry.isIntersecting && !hero3dState.animationId) {
            animateHero();
          }
        });
      },
      { threshold: 0.05 }
    );
    observer.observe(heroSection);
  }

  // Animation Loop
  let clock = new THREE.Clock();
  function animateHero() {
    if (hero3dState.isPaused) {
      hero3dState.animationId = null;
      return;
    }
    hero3dState.animationId = requestAnimationFrame(animateHero);

    const elapsed = clock.getElapsedTime();

    // Smooth mouse lerping
    hero3dState.currentMouseX += (hero3dState.targetMouseX - hero3dState.currentMouseX) * 0.04;
    hero3dState.currentMouseY += (hero3dState.targetMouseY - hero3dState.currentMouseY) * 0.04;

    // Core rotations
    if (coreGroup) {
      coreGroup.rotation.y = elapsed * 0.18 + hero3dState.currentMouseX * 0.4;
      coreGroup.rotation.x = Math.sin(elapsed * 0.12) * 0.15 + hero3dState.currentMouseY * 0.3;
      coreGroup.position.y = Math.sin(elapsed * 0.8) * 0.25;
      ring1.rotation.z = elapsed * 0.25;
      ring2.rotation.z = -elapsed * 0.2;
      innerMesh.rotation.y = -elapsed * 0.35;
    }

    // Grid subtle movement
    gridHelper.position.z = (elapsed * 0.4) % 1;

    // Scan ring pulse
    if (scanRing) {
      const pulse = ((elapsed * 0.5) % 1);
      scanRing.scale.set(pulse * 2.5 + 0.2, pulse * 2.5 + 0.2, 1);
      scanMat.opacity = 0.12 * (1 - pulse);
    }

    // Subtle particle drift
    if (particleSystem) {
      particleSystem.rotation.y = elapsed * 0.02;
    }

    // Camera tilt
    camera.position.x = hero3dState.currentMouseX * 1.2;
    camera.position.y = 2.5 + hero3dState.currentMouseY * 0.8;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
  }

  hero3dState.isInitialized = true;
  animateHero();
}

function onHeroResize() {
  const canvas = document.getElementById("hero-three-canvas");
  const heroSection = document.getElementById("hero");
  if (!canvas || !heroSection || !hero3dState.renderer || !hero3dState.camera) return;

  const width = heroSection.clientWidth || window.innerWidth;
  const height = heroSection.clientHeight || window.innerHeight;

  hero3dState.camera.aspect = width / height;
  hero3dState.camera.updateProjectionMatrix();
  hero3dState.renderer.setSize(width, height);
}

/* ══════════════════════════════════════════════════════════════════════════
   INITIALISATION
════════════════════════════════════════════════════════════════════════════ */
async function init() {
  // Initialize Phase 10 Hero 3D WebGL Scene
  initHero3D();

  // Health check
  await refreshHealth();
  dom.btnRefreshHealth.addEventListener("click", refreshHealth);

  // Load existing cases
  await loadCases();

  // Case selector change
  dom.caseSelect.addEventListener("change", () => {
    selectCase(dom.caseSelect.value);
  });

  // Create case button
  dom.btnCreateCase.addEventListener("click", createCase);

  // Tab buttons
  dom.tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      activateTab(btn.dataset.tab);
      // Auto-scroll to workspace if clicked from above
      const ws = document.getElementById("investigation-workspace");
      if (ws && window.scrollY < ws.offsetTop - 120) {
        ws.scrollIntoView({ behavior: "smooth" });
      }
    });
  });

  // Smooth scroll navigation for all anchor links
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      const targetId = this.getAttribute("href");
      if (!targetId || targetId === "#") return;
      const targetEl = document.querySelector(targetId);
      if (targetEl) {
        e.preventDefault();
        targetEl.scrollIntoView({ behavior: "smooth" });
      }
    });
  });

  // Topbar scrollspy active link tracking
  const navLinks = document.querySelectorAll(".topbar__nav .nav-link");
  const navSections = [
    document.getElementById("hero"),
    document.getElementById("story-tour"),
    document.getElementById("investigation-workspace"),
  ].filter(Boolean);

  if (navSections.length > 0) {
    window.addEventListener("scroll", () => {
      const scrollPos = window.scrollY + 200;
      navSections.forEach((sec) => {
        if (
          scrollPos >= sec.offsetTop &&
          scrollPos < sec.offsetTop + sec.offsetHeight
        ) {
          const id = sec.getAttribute("id");
          navLinks.forEach((link) => {
            link.classList.toggle(
              "nav-link--active",
              link.getAttribute("href") === `#${id}`
            );
          });
        }
      });
    });
  }

  // Drag & drop / file input
  initDragDrop();

  // Image analysis button
  if (dom.btnRunImageAnalysis) {
    dom.btnRunImageAnalysis.addEventListener("click", runImageAnalysis);
  }

  // Audio analysis button (Phase 4)
  if (dom.btnRunAudioAnalysis) {
    dom.btnRunAudioAnalysis.addEventListener("click", runAudioTranscription);
  }

  // Video analysis button (Phase 5)
  if (dom.btnRunVideoAnalysis) {
    dom.btnRunVideoAnalysis.addEventListener("click", runVideoAnalysis);
  }

  // Multimodal Fusion button (Phase 6)
  if (dom.btnRunFusion) {
    dom.btnRunFusion.addEventListener("click", runFusionAnalysis);
  }

  // Forensic PDF download button
  if (dom.btnDownloadPdf) {
    dom.btnDownloadPdf.addEventListener("click", downloadForensicPdf);
  }

  // Phase 7 Chat assistant listeners
  if (dom.btnChatSend) {
    dom.btnChatSend.addEventListener("click", (e) => {
      e.preventDefault();
      sendChatMessage();
    });
  }
  if (dom.chatInput) {
    dom.chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }
  if (dom.btnClearChat) {
    dom.btnClearChat.addEventListener("click", clearChat);
  }
  if (dom.chatSuggestions) {
    dom.chatSuggestions.querySelectorAll(".chip-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        sendChatMessage(btn.dataset.query);
      });
    });
  }

  // Phase 8 3D Scene Controls
  if (dom.btnScene3dResetCam) {
    dom.btnScene3dResetCam.addEventListener("click", () => {
      if (scene3dState.camera && scene3dState.controls) {
        scene3dState.camera.position.set(0, 14, 20);
        scene3dState.controls.target.set(0, 0, 0);
        scene3dState.controls.update();
      }
    });
  }

  if (dom.btnScene3dToggleGrid) {
    dom.btnScene3dToggleGrid.addEventListener("click", () => {
      scene3dState.showGrid = !scene3dState.showGrid;
      if (scene3dState.gridHelper) {
        scene3dState.gridHelper.visible = scene3dState.showGrid;
      }
      dom.btnScene3dToggleGrid.textContent = `📐 Grid: ${scene3dState.showGrid ? "On" : "Off"}`;
    });
  }

  if (dom.btnScene3dToggleLabels) {
    dom.btnScene3dToggleLabels.addEventListener("click", () => {
      scene3dState.showLabels = !scene3dState.showLabels;
      dom.btnScene3dToggleLabels.textContent = `🏷️ Labels: ${scene3dState.showLabels ? "On" : "Off"}`;
      filterSceneObjects();
    });
  }

  if (dom.btnScene3dRefresh) {
    dom.btnScene3dRefresh.addEventListener("click", () => {
      if (state.activeCaseId) {
        loadScene3d(state.activeCaseId);
      }
    });
  }

  if (dom.scene3dFilterCategory) {
    dom.scene3dFilterCategory.addEventListener("change", filterSceneObjects);
  }

  if (dom.scene3dFilterEvidence) {
    dom.scene3dFilterEvidence.addEventListener("change", filterSceneObjects);
  }

  if (dom.scene3dConfSlider) {
    dom.scene3dConfSlider.addEventListener("input", (e) => {
      if (dom.scene3dConfVal) {
        dom.scene3dConfVal.textContent = `${e.target.value}%`;
      }
      filterSceneObjects();
    });
  }

  if (dom.btnCloseDetCard) {
    dom.btnCloseDetCard.addEventListener("click", () => {
      if (dom.scene3dDetailsCard) {
        dom.scene3dDetailsCard.style.display = "none";
      }
    });
  }

  // Window resize redrawing for responsive bounding boxes
  window.addEventListener("resize", () => {
    if (state.activeEvidenceId) {
      const ev = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
      if (ev && ev.analysis_json) {
        drawBoundingBoxes(ev.analysis_json);
      }
    }
  });

  // Default tab
  activateTab("image");
}

document.addEventListener("DOMContentLoaded", init);
