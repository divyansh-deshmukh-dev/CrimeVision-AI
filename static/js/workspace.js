/**
 * workspace.js — CrimeVision AI Investigation Workspace Controller
 * Professional digital forensics interface logic.
 */

"use strict";

/* ── Professional SVG Icon Library ────────────────────────────────────────── */
const SVG_ICONS = {
  image: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
  audio: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`,
  video: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>`,
  check: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  info: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  error: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
  clock: `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  copy: `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  chevronRight: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>`,
};

/* ── API Endpoints ────────────────────────────────────────────────────────── */
const API = {
  health:        "/api/health",
  cases:         "/api/cases",
  evidence:      (cid) => `/api/cases/${cid}/evidence`,
  deleteEvidence:(cid, eid) => `/api/cases/${cid}/evidence/${eid}`,
  evidenceFile:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/file`,
  analyzeImage:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/analyze/image`,
  restoreSeededSample: (cid, eid) => `/api/cases/${cid}/evidence/${eid}/restore_seeded_sample`,
  analyzeAudio:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/analyze/audio`,
  audioIntelligence: (cid, eid) => `/api/cases/${cid}/evidence/${eid}/analyze/audio/intelligence`,
  analyzeVideo:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/analyze/video`,
  analyzeFusion: (cid) => `/api/cases/${cid}/analyze/fusion`,
  caseReport:    (cid) => `/api/cases/${cid}/reports`,
  reportPdf:     (cid) => `/api/cases/${cid}/reports/pdf`,
  chat:          (cid) => `/api/cases/${cid}/chat`,
  chatEvidence:  (cid, eid) => `/api/cases/${cid}/evidence/${eid}/chat`,
  chatHistory:   (cid) => `/api/cases/${cid}/chat/history`,
  spatialVisualization: (cid) => `/api/cases/${cid}/visualization/spatial`,
};

/* ── DOM Cache ────────────────────────────────────────────────────────────── */
const dom = {
  // Case Controls
  caseSelect:           document.getElementById("case-select"),
  workspaceCaseName:    document.getElementById("workspace-case-name"),
  caseStatusDot:        document.getElementById("case-status-dot"),
  btnOpenCreateModal:   document.getElementById("btn-open-create-modal"),
  modalNewCase:         document.getElementById("modal-new-case"),
  btnCloseCaseModal:    document.getElementById("btn-close-case-modal"),
  btnCancelCaseModal:   document.getElementById("btn-cancel-case-modal"),
  btnCreateCase:        document.getElementById("btn-create-case"),
  newCaseName:          document.getElementById("new-case-name"),
  newCaseDesc:          document.getElementById("new-case-desc"),
  createCaseMsg:        document.getElementById("create-case-msg"),

  // Navigation & Feature Views
  navItems:             document.querySelectorAll(".nav-item"),
  featureViews:         document.querySelectorAll(".feature-view"),
  sidebarEvidenceCount: document.getElementById("sidebar-evidence-count"),

  // Overview View
  overviewCaseHeading:  document.getElementById("overview-case-heading"),
  overviewCaseSub:      document.getElementById("overview-case-sub"),
  overviewCaseId:       document.getElementById("overview-case-id"),
  overviewCaseCreated:  document.getElementById("overview-case-created"),
  overviewCaseDesc:     document.getElementById("overview-case-desc"),
  statTotalEvidence:    document.getElementById("stat-total-evidence"),
  statEvidenceMeta:     document.getElementById("stat-evidence-meta"),
  statImageCount:       document.getElementById("stat-image-count"),
  statAudioCount:       document.getElementById("stat-audio-count"),
  statVideoCount:       document.getElementById("stat-video-count"),
  overviewEvidenceGrid: document.getElementById("overview-evidence-grid"),
  overviewEvidenceEmpty:document.getElementById("overview-evidence-empty"),
  btnQuickUpload:       document.getElementById("btn-quick-upload"),
  btnQuickFusion:       document.getElementById("btn-quick-fusion"),
  btnViewAllEvidence:   document.getElementById("btn-view-all-evidence"),

  // Evidence Ingestion View
  uploadZone:           document.getElementById("upload-zone"),
  fileInput:            document.getElementById("file-input"),
  uploadStatus:         document.getElementById("upload-status"),
  evidenceList:         document.getElementById("evidence-list"),
  inventoryCountBadge:  document.getElementById("inventory-count-badge"),

  // Image Analysis View
  panelImage:           document.getElementById("panel-image"),
  selectImageEvidence:  document.getElementById("select-image-evidence"),
  imageFilenameDisplay: document.getElementById("image-filename-display"),
  evidenceImage:        document.getElementById("evidence-image"),
  bboxCanvas:           document.getElementById("bbox-canvas"),
  imageStageBox:        document.getElementById("image-stage-box"),
  imageCanvasContainer: document.getElementById("image-canvas-container"),
  imageEmptyPlaceholder:document.getElementById("image-empty-placeholder"),
  btnRunImageAnalysis:  document.getElementById("btn-run-image-analysis"),
  imageStatusBadge:     document.getElementById("image-status-badge"),
  rtdetrCountBadge:     document.getElementById("rtdetr-count-badge"),
  rtdetrContent:        document.getElementById("rtdetr-content"),
  blipContent:          document.getElementById("blip-content"),
  clipContent:          document.getElementById("clip-content"),
  imgStatTotal:         document.getElementById("img-stat-total"),
  imgStatPersons:       document.getElementById("img-stat-persons"),
  imgStatVehicles:      document.getElementById("img-stat-vehicles"),
  imgStatWeapons:       document.getElementById("img-stat-weapons"),
  imgStatScene:         document.getElementById("img-stat-scene"),
  imageSubtabBtns:      document.querySelectorAll(".image-subtab-btn"),
  imageSubtabPanels:    document.querySelectorAll(".image-subtab-panel"),
  imgAiSceneSummaryContent: document.getElementById("img-ai-scene-summary-content"),
  imgVisualSummaryContent:  document.getElementById("img-visual-summary-content"),
  imgActionsDetectedContent:document.getElementById("img-actions-detected-content"),
  imgFactsCountBadge:   document.getElementById("img-facts-count-badge"),
  imgFactsTableContainer:document.getElementById("img-facts-table-container"),
  imgScenariosContent:  document.getElementById("img-scenarios-content"),
  imgChatStatus:        document.getElementById("img-chat-status"),
  imgChatChips:         document.getElementById("img-chat-chips"),
  imgChatResponseArea:  document.getElementById("img-chat-response-area"),
  imgChatPlaceholder:   document.getElementById("img-chat-placeholder"),
  imgChatForm:          document.getElementById("img-chat-form"),
  imgChatInput:         document.getElementById("img-chat-input"),
  btnImgChatSend:       document.getElementById("btn-img-chat-send"),
  imgChatSendText:      document.getElementById("img-chat-send-text"),
  imgChatSendSpinner:   document.getElementById("img-chat-send-spinner"),

  // Audio Analysis View
  panelAudio:           document.getElementById("panel-audio"),
  selectAudioEvidence:  document.getElementById("select-audio-evidence"),
  audioFilenameDisplay: document.getElementById("audio-filename-display"),
  evidenceAudio:        document.getElementById("evidence-audio"),
  audioEmptyPlaceholder:document.getElementById("audio-empty-placeholder"),
  btnRunAudioAnalysis:  document.getElementById("btn-run-audio-analysis"),
  audioStatusBadge:     document.getElementById("audio-status-badge"),
  whisperLangBadge:     document.getElementById("whisper-lang-badge"),
  whisperContent:       document.getElementById("whisper-content"),
  audioTranscriptContainer: document.getElementById("audio-transcript-container"),
  audioSegmentsList:    document.getElementById("audio-segments-list"),
  audioMetricsPanel:    document.getElementById("audio-metrics-panel"),
  audioStatDuration:    document.getElementById("audio-stat-duration"),
  audioStatSr:          document.getElementById("audio-stat-sr"),
  audioStatChannels:    document.getElementById("audio-stat-channels"),
  audioStatStatus:      document.getElementById("audio-stat-status"),
  audioCustodyEid:      document.getElementById("audio-custody-eid"),
  audioCustodyHash:     document.getElementById("audio-custody-hash"),
  audioSegmentCountBadge: document.getElementById("audio-segment-count-badge"),
  audioIntelReportCard: document.getElementById("audio-intel-report-card"),
  audioIntelBadge:      document.getElementById("audio-intel-badge"),
  audioAiSummaryContent:document.getElementById("audio-ai-summary-content"),
  audioEventTypeBadge:  document.getElementById("audio-event-type-badge"),
  audioEventTypeDetail: document.getElementById("audio-event-type-detail"),
  audioLocationContent: document.getElementById("audio-location-content"),
  audioLocationText:    document.getElementById("audio-location-text"),
  audioActiveLangBadge: document.getElementById("audio-active-lang-badge"),
  audioLangTabBtns:     document.querySelectorAll(".audio-lang-tab-btn"),
  audioTranslationDisplay: document.getElementById("audio-translation-display"),
  audioTimelineCard:    document.getElementById("audio-timeline-card"),
  audioTimelineCountBadge: document.getElementById("audio-timeline-count-badge"),
  audioTimelineContainer:  document.getElementById("audio-timeline-container"),
  audioChatStatus:      document.getElementById("audio-chat-status"),
  audioChatChips:       document.getElementById("audio-chat-chips"),
  audioChatResponseArea:document.getElementById("audio-chat-response-area"),
  audioChatPlaceholder: document.getElementById("audio-chat-placeholder"),
  audioChatForm:        document.getElementById("audio-chat-form"),
  audioChatInput:       document.getElementById("audio-chat-input"),
  btnAudioChatSend:     document.getElementById("btn-audio-chat-send"),
  audioChatSendText:    document.getElementById("audio-chat-send-text"),
  audioChatSendSpinner: document.getElementById("audio-chat-send-spinner"),
  audioSubtabBtns:      document.querySelectorAll(".audio-subtab-btn"),
  audioEntitiesContent: document.getElementById("audio-entities-content"),
  audioSegmentsPlaceholder: document.getElementById("audio-segments-placeholder"),
  audioCustodyCase:     document.getElementById("audio-custody-case"),
  audioCustodyFilename: document.getElementById("audio-custody-filename"),
  audioDetailFormat:    document.getElementById("audio-detail-format"),
  audioDetailFilesize:  document.getElementById("audio-detail-filesize"),
  audioDetailUploaded:  document.getElementById("audio-detail-uploaded"),

  // Video Analysis View
  panelVideo:           document.getElementById("panel-video"),
  selectVideoEvidence:  document.getElementById("select-video-evidence"),
  videoFilenameDisplay: document.getElementById("video-filename-display"),
  evidenceVideo:        document.getElementById("evidence-video"),
  videoCanvasContainer: document.getElementById("video-canvas-container"),
  videoStageBox:        document.getElementById("video-stage-box"),
  videoBboxCanvas:      document.getElementById("video-bbox-canvas"),
  btnVideoFullscreen:   document.getElementById("btn-video-fullscreen"),
  videoEmptyPlaceholder:document.getElementById("video-empty-placeholder"),
  videoSampleInterval:  document.getElementById("video-sample-interval"),
  btnRunVideoAnalysis:  document.getElementById("btn-run-video-analysis"),
  videoStatusBadge:     document.getElementById("video-status-badge"),
  videoCountBadge:      document.getElementById("video-count-badge"),
  videoContent:         document.getElementById("video-content"),
  videoTimelineContainer: document.getElementById("video-timeline-container"),
  videoFramesList:      document.getElementById("video-frames-list"),
  videoSceneIntelCard:           document.getElementById("video-scene-intel-card"),
  videoSceneIntelContent:        document.getElementById("video-scene-intel-content"),
  videoSceneIntelPlaceholder:    document.getElementById("video-scene-intel-placeholder"),
  videoSceneTypeBadge:           document.getElementById("video-scene-type-badge"),
  videoIntelObjectsCount:        document.getElementById("video-intel-objects-count"),
  videoObjectsDetectedContainer: document.getElementById("video-objects-detected-container"),
  videoPeoplePeak:               document.getElementById("video-people-peak"),
  videoPeopleTotal:              document.getElementById("video-people-total"),
  videoPeopleAvg:                document.getElementById("video-people-avg"),
  videoPeopleSummary:            document.getElementById("video-people-summary"),
  videoSceneName:                document.getElementById("video-scene-name"),
  videoSceneConf:                document.getElementById("video-scene-conf"),
  videoSceneBasis:               document.getElementById("video-scene-basis"),
  videoObservableActionsList:    document.getElementById("video-observable-actions-list"),
  videoSummaryCard:              document.getElementById("video-visual-summary-card"),
  videoSummaryContent:           document.getElementById("video-summary-content"),
  videoSummaryPlaceholder:       document.getElementById("video-summary-placeholder"),
  videoSummaryStatus:            document.getElementById("video-summary-status"),
  videoSummaryNarrative:         document.getElementById("video-summary-narrative"),
  videoDirectObservationsList:   document.getElementById("video-direct-observations-list"),
  videoAiInterpretationsList:    document.getElementById("video-ai-interpretations-list"),
  videoUncertaintyDetails:       document.getElementById("video-uncertainty-details"),
  videoTimelinePlaceholder:      document.getElementById("video-timeline-placeholder"),
  videoTimelineCountBadge:       document.getElementById("video-timeline-count-badge"),
  videoVehiclesPeak:             document.getElementById("video-vehicles-peak"),
  videoVehiclesTotal:            document.getElementById("video-vehicles-total"),
  videoVehiclesAvg:              document.getElementById("video-vehicles-avg"),
  videoVehiclesSummary:          document.getElementById("video-vehicles-summary"),
  videoFrameSummariesList:       document.getElementById("video-frame-summaries-list"),
  videoTabPanelIntel:            document.getElementById("video-tab-panel-intel"),
  videoTabPanelSummary:          document.getElementById("video-tab-panel-summary"),
  videoTabPanelTimeline:         document.getElementById("video-tab-panel-timeline"),

  // Multimodal Fusion View
  panelFusion:          document.getElementById("panel-fusion"),
  btnRunFusion:         document.getElementById("btn-run-fusion"),
  fusionStatusBadge:    document.getElementById("fusion-status-badge"),
  covImgBadge:          document.getElementById("cov-img-badge"),
  covAudBadge:          document.getElementById("cov-aud-badge"),
  covVidBadge:          document.getElementById("cov-vid-badge"),
  fusionScopeSummary:   document.getElementById("fusion-scope-summary"),
  fusionAssocCount:     document.getElementById("fusion-assoc-count"),
  fusionAssociationsContent: document.getElementById("fusion-associations-content"),
  fusionTemporalCount:  document.getElementById("fusion-temporal-count"),
  fusionTemporalContent:document.getElementById("fusion-temporal-content"),
  fusionConflictCount:  document.getElementById("fusion-conflict-count"),
  fusionContradictionsContent: document.getElementById("fusion-contradictions-content"),
  fusionQuestionsContent:document.getElementById("fusion-questions-content"),

  // 3D Spatial Scene View
  panelScene3d:         document.getElementById("panel-scene3d"),
  scene3dViewport:      document.getElementById("scene3d-viewport"),
  threejsCanvas:        document.getElementById("threejs-canvas"),
  scene3dEmptyState:    document.getElementById("scene3d-empty-state"),
  scene3dEmptyText:     document.getElementById("scene3d-empty-text"),
  scene3dLoading:       document.getElementById("scene3d-loading"),
  scene3dLegend:        document.getElementById("scene3d-legend"),
  scene3dLegendList:    document.getElementById("scene3d-legend-list"),
  scene3dDetailsCard:   document.getElementById("scene3d-details-card"),
  btnScene3dResetCam:   document.getElementById("btn-scene3d-reset-cam"),
  btnScene3dToggleGrid: document.getElementById("btn-scene3d-toggle-grid"),
  btnScene3dToggleLabels: document.getElementById("btn-scene3d-toggle-labels"),
  btnScene3dRefresh:    document.getElementById("btn-scene3d-refresh"),
  scene3dFilterCategory:document.getElementById("scene3d-filter-category"),
  scene3dFilterEvidence:document.getElementById("scene3d-filter-evidence"),
  scene3dConfSlider:    document.getElementById("scene3d-conf-slider"),
  scene3dConfVal:       document.getElementById("scene3d-conf-val"),
  scene3dCountBadge:    document.getElementById("scene3d-count-badge"),
  detCardLabel:         document.getElementById("det-card-label"),
  detCardConf:          document.getElementById("det-card-conf"),
  detCardEvidence:      document.getElementById("det-card-evidence"),
  detCardTimestampRow:  document.getElementById("det-card-timestamp-row"),
  detCardTimestamp:     document.getElementById("det-card-timestamp"),
  detCardBbox:          document.getElementById("det-card-bbox"),
  detCardPos:           document.getElementById("det-card-pos"),
  btnCloseDetCard:      document.getElementById("btn-close-det-card"),
  btnDetCardNavigate:   document.getElementById("btn-det-card-navigate"),

  // Forensic Reports
  btnDownloadPdf:       document.getElementById("btn-download-pdf"),
  reportCaseIdDisplay:  document.getElementById("report-case-id-display"),
  reportEvidenceSummary:document.getElementById("report-evidence-summary"),
  reportFindingsSummary:document.getElementById("report-findings-summary"),
  reportFusionSummary:  document.getElementById("report-fusion-summary"),

  // AI Assistant Panel
  wsChatPanel:          document.getElementById("ws-chat-panel"),
  btnToggleAssistant:   document.getElementById("btn-toggle-assistant"),
  btnCloseAssistant:    document.getElementById("btn-close-assistant"),
  chatMessages:         document.getElementById("chat-messages"),
  chatEmptyHint:        document.getElementById("chat-empty-hint"),
  chatForm:             document.getElementById("chat-form"),
  chatInput:            document.getElementById("chat-input"),
  btnChatSend:          document.getElementById("btn-chat-send"),
  chatSendText:         document.getElementById("chat-send-text"),
  chatSendSpinner:      document.getElementById("chat-send-spinner"),
  btnClearChat:         document.getElementById("btn-clear-chat"),
  chatStatusBadge:      document.getElementById("chat-status-badge"),
  chatSuggestions:      document.getElementById("chat-suggestions"),
  chatPanelBackdrop:    document.getElementById("chat-panel-backdrop"),

  // Toast Container
  toastContainer:       document.getElementById("toast-container"),
  btnRefreshHealth:     document.getElementById("btn-refresh-health"),
  healthStatusLabel:    document.getElementById("health-status-label"),
  healthStatusPill:     document.getElementById("health-status-pill"),
};

/* ── Application State ────────────────────────────────────────────────────── */
const state = {
  activeCaseId: null,
  activeEvidenceId: null,
  activeView: "overview",
  cases: [],
  evidence: [],
  reports: [],
  currentImageAnalysis: null,
  currentVideoAnalysis: null,
  activeVideoTimestamp: null,
  currentAudioAnalysis: null,
  currentAudioTranslations: null,
  activeAudioLang: "original",
};

/* ── Utility Helpers ──────────────────────────────────────────────────────── */
function escapeHtml(str) {
  if (typeof str !== "string") return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(message, type = "info", durationMs = 4000) {
  if (!dom.toastContainer) return;
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  const iconSvg = SVG_ICONS[type] || SVG_ICONS.info;
  toast.innerHTML = `<span class="toast-icon">${iconSvg}</span><span>${escapeHtml(message)}</span>`;
  dom.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(10px)";
    setTimeout(() => toast.remove(), 250);
  }, durationMs);
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
      // Session expired or unauthenticated
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
      return { ok: false, status: 401, data: { error: "Authentication required." } };
    }
    const data = await res.json().catch(() => ({}));

    if (res.status >= 500 && url === API.health) {
      setHealthDisconnected("Core Engine: Degraded (Server Error)");
    }

    if (res.status === 403 && !opts.silent403) {
      const msg = data.error || "Access Denied: You do not have permission to perform this action.";
      showToast(msg, "error");
    }

    return { ok: res.ok, status: res.status, data };
  } catch (err) {
    if (url === API.health) {
      setHealthDisconnected("Core Engine: Disconnected");
    }
    return { ok: false, status: 0, data: { error: err.message } };
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   VIEW NAVIGATION CONTROLLER
════════════════════════════════════════════════════════════════════════════ */
function switchView(viewName) {
  state.activeView = viewName;

  // Update sidebar active buttons
  dom.navItems.forEach(item => {
    item.classList.toggle("nav-item--active", item.dataset.view === viewName);
  });

  // Toggle active feature view
  dom.featureViews.forEach(view => {
    const isTarget = view.id === `view-${viewName}`;
    view.classList.toggle("feature-view--active", isTarget);
    view.style.display = isTarget ? "block" : "none";
  });

  // Special triggers for view activation
  if (viewName === "scene3d") {
    if (!scene3dState.isInitialized) {
      initThreeJs();
    }
    if (state.activeCaseId) {
      loadScene3d(state.activeCaseId);
    }
    setTimeout(() => {
      if (scene3dState.renderer && dom.scene3dViewport) {
        const w = dom.scene3dViewport.clientWidth || 800;
        const h = dom.scene3dViewport.clientHeight || 560;
        scene3dState.camera.aspect = w / h;
        scene3dState.camera.updateProjectionMatrix();
        scene3dState.renderer.setSize(w, h);
      }
    }, 100);
  }

  if (viewName === "image") {
    const cur = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
    if (!cur || cur.modality !== "image") {
      const firstImg = state.evidence.find(e => e.modality === "image");
      if (firstImg) {
        selectEvidence(firstImg.evidence_id, false);
      }
    }
    if (state.currentImageAnalysis) {
      setTimeout(() => {
        requestAnimationFrame(() => drawBoundingBoxes(state.currentImageAnalysis));
      }, 50);
    }
  } else if (viewName === "audio") {
    const cur = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
    if (!cur || cur.modality !== "audio") {
      const firstAud = state.evidence.find(e => e.modality === "audio");
      if (firstAud) {
        selectEvidence(firstAud.evidence_id, false);
      }
    }
  } else if (viewName === "video") {
    const cur = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
    if (!cur || cur.modality !== "video") {
      const firstVid = state.evidence.find(e => e.modality === "video");
      if (firstVid) {
        selectEvidence(firstVid.evidence_id, false);
      }
    }
    if (state.currentVideoAnalysis) {
      setTimeout(() => {
        requestAnimationFrame(() => updateVideoOverlay());
      }, 50);
    }
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   CASE MANAGEMENT
════════════════════════════════════════════════════════════════════════════ */
async function loadCases() {
  const { ok, data } = await apiFetch(API.cases);
  if (!ok) {
    showToast("Failed to fetch cases list.", "error");
    return;
  }

  // Ensure legacy read-only demo cases are excluded from the normal user workspace
  const allCases = data.cases || [];
  state.cases = allCases.filter(c => !c.is_readonly && c.case_id !== "case_demo_sentinel" && c.demo_type !== "legacy" && !c.is_demo);
  renderCaseOptions();

  // If no case is active, auto-select a suitable existing writable case
  if (!state.activeCaseId) {
    if (state.cases.length > 0) {
      const defaultCase = state.cases[0];
      dom.caseSelect.value = defaultCase.case_id;
      await selectCase(defaultCase.case_id);
    } else {
      await selectCase(null);
      // Provide a clear option to create a new case when no writable cases exist
      dom.overviewCaseHeading.textContent = "Welcome to CrimeVision AI";
      dom.overviewCaseSub.textContent = "No active investigation cases found. Create a new case container to upload and inspect forensic evidence.";
      dom.evidenceList.innerHTML = `
        <li style="padding: 2.5rem 1rem; text-align: center; color: var(--text-muted);">
          <div style="font-size: 1.05rem; font-weight: 600; color: #FFF; margin-bottom: 8px;">No Active Investigation Case</div>
          <p style="margin-bottom: 16px; font-size: 0.88rem; max-width: 420px; margin-left: auto; margin-right: auto;">
            You are logged into an active workspace. Create your first case container to begin uploading images, wiretaps, and surveillance video.
          </p>
          <button class="btn btn-primary btn-sm" id="btn-empty-prompt-create-case" onclick="dom.modalCreateCase.classList.add('modal-backdrop--open'); dom.newCaseName.focus();">
            + Create New Investigation Case
          </button>
        </li>
      `;
    }
  } else {
    const stillExists = state.cases.find(c => c.case_id === state.activeCaseId);
    if (!stillExists) {
      if (state.cases.length > 0) {
        dom.caseSelect.value = state.cases[0].case_id;
        await selectCase(state.cases[0].case_id);
      } else {
        await selectCase(null);
      }
    }
  }
}

function renderCaseOptions() {
  dom.caseSelect.innerHTML = `<option value="">— Select or create case —</option>`;
  if (state.cases.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "+ Create your first case...";
    dom.caseSelect.appendChild(opt);
    return;
  }

  state.cases.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.case_id;
    opt.textContent = `${c.name} (${c.case_id})`;
    if (c.case_id === state.activeCaseId) opt.selected = true;
    dom.caseSelect.appendChild(opt);
  });
}

async function selectCase(caseId) {
  state.activeCaseId = caseId;
  state.activeEvidenceId = null;

  if (!caseId) {
    dom.workspaceCaseName.textContent = "No active case";
    dom.caseStatusDot.className = "status-dot status-dot--inactive";
    dom.sidebarEvidenceCount.textContent = "0";
    dom.statTotalEvidence.textContent = "0";
    dom.statImageCount.textContent = "0";
    dom.statAudioCount.textContent = "0";
    dom.statVideoCount.textContent = "0";
    dom.overviewCaseHeading.textContent = "Investigation Case Overview";
    dom.overviewCaseSub.textContent = "Select an active investigation case to inspect evidence status and analytics.";
    dom.overviewCaseId.textContent = "—";
    dom.overviewCaseCreated.textContent = "—";
    dom.overviewCaseDesc.textContent = "No case selected";
    dom.evidenceList.innerHTML = `<li class="muted" style="padding:1rem; text-align:center;">Select an active case to view evidence artifacts.</li>`;
    disableChatAssistant();
    return;
  }

  const currentCase = state.cases.find(c => c.case_id === caseId);
  const name = currentCase ? currentCase.name : caseId;

  dom.workspaceCaseName.textContent = name;
  dom.caseStatusDot.className = "status-dot status-dot--active";
  dom.overviewCaseHeading.textContent = `Case: ${name}`;
  dom.overviewCaseSub.textContent = `Case ID: ${caseId} · Comprehensive Multimodal Forensic Ledger`;
  dom.overviewCaseId.textContent = caseId;
  dom.overviewCaseCreated.textContent = currentCase && currentCase.created_at ? new Date(currentCase.created_at).toLocaleString() : "Active";
  dom.overviewCaseDesc.textContent = (currentCase && currentCase.description) ? currentCase.description : "No descriptive notes provided.";

  if (dom.reportCaseIdDisplay) dom.reportCaseIdDisplay.textContent = caseId;

  await loadEvidence(caseId);
  await loadChatHistory(caseId);

  if (state.activeView === "scene3d") {
    loadScene3d(caseId);
  }
}

async function createCase() {
  const name = (dom.newCaseName.value || "").trim();
  const desc = (dom.newCaseDesc.value || "").trim();

  if (!name) {
    dom.createCaseMsg.textContent = "Case title is required.";
    dom.createCaseMsg.className = "form-hint form-hint--error";
    return;
  }

  dom.btnCreateCase.disabled = true;
  dom.createCaseMsg.textContent = "Creating case container…";
  dom.createCaseMsg.className = "form-hint";

  const { ok, status, data } = await apiFetch(API.cases, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description: desc }),
  });

  dom.btnCreateCase.disabled = false;

  if (ok) {
    showToast(`Case container '${name}' created.`, "success");
    dom.modalNewCase.style.display = "none";
    dom.newCaseName.value = "";
    dom.newCaseDesc.value = "";
    dom.createCaseMsg.textContent = "";

    await loadCases();
    dom.caseSelect.value = data.case.case_id;
    await selectCase(data.case.case_id);
  } else {
    dom.createCaseMsg.textContent = data.error || `Error ${status}: Creation failed.`;
    dom.createCaseMsg.className = "form-hint form-hint--error";
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   EVIDENCE INGESTION & MANAGEMENT
══════════════════════════════════════════════════════════════════════════ */
async function loadEvidence(caseId) {
  if (!caseId) return;

  const { ok, data } = await apiFetch(API.evidence(caseId));
  if (!ok) {
    showToast("Failed to load evidence items.", "error");
    return;
  }

  state.evidence = data.evidence || [];
  updateEvidenceCounts();
  populateModalitySelects();
  renderEvidenceInventory();
  renderOverviewEvidenceStrip();
}

function getEvidenceDisplayName(item) {
  if (!item) return "Evidence File";
  if (item.original_name) return item.original_name;
  if (item.filename) {
    const parts = item.filename.split(/[\\/]/);
    return parts[parts.length - 1];
  }
  return item.evidence_id || "Evidence File";
}

function populateModalitySelects() {
  const images = state.evidence.filter(e => e.modality === "image");
  const audios = state.evidence.filter(e => e.modality === "audio");
  const videos = state.evidence.filter(e => e.modality === "video");

  // 1. Image Select
  if (dom.selectImageEvidence) {
    if (images.length === 0) {
      dom.selectImageEvidence.innerHTML = `<option value="">No images available</option>`;
      dom.selectImageEvidence.disabled = true;
    } else {
      dom.selectImageEvidence.disabled = false;
      dom.selectImageEvidence.innerHTML = `<option value="">-- Choose Image (${images.length}) --</option>` +
        images.map(img => `<option value="${img.evidence_id}" ${img.evidence_id === state.activeEvidenceId ? "selected" : ""}>${escapeHtml(getEvidenceDisplayName(img))}</option>`).join("");
      if (state.activeEvidenceId && images.some(img => img.evidence_id === state.activeEvidenceId)) {
        dom.selectImageEvidence.value = state.activeEvidenceId;
      }
    }
  }

  // 2. Audio Select
  if (dom.selectAudioEvidence) {
    if (audios.length === 0) {
      dom.selectAudioEvidence.innerHTML = `<option value="">No audio available</option>`;
      dom.selectAudioEvidence.disabled = true;
    } else {
      dom.selectAudioEvidence.disabled = false;
      dom.selectAudioEvidence.innerHTML = `<option value="">-- Choose Audio (${audios.length}) --</option>` +
        audios.map(aud => `<option value="${aud.evidence_id}" ${aud.evidence_id === state.activeEvidenceId ? "selected" : ""}>${escapeHtml(getEvidenceDisplayName(aud))}</option>`).join("");
      if (state.activeEvidenceId && audios.some(aud => aud.evidence_id === state.activeEvidenceId)) {
        dom.selectAudioEvidence.value = state.activeEvidenceId;
      }
    }
  }

  // 3. Video Select
  if (dom.selectVideoEvidence) {
    if (videos.length === 0) {
      dom.selectVideoEvidence.innerHTML = `<option value="">No video available</option>`;
      dom.selectVideoEvidence.disabled = true;
    } else {
      dom.selectVideoEvidence.disabled = false;
      dom.selectVideoEvidence.innerHTML = `<option value="">-- Choose Video (${videos.length}) --</option>` +
        videos.map(vid => `<option value="${vid.evidence_id}" ${vid.evidence_id === state.activeEvidenceId ? "selected" : ""}>${escapeHtml(getEvidenceDisplayName(vid))}</option>`).join("");
      if (state.activeEvidenceId && videos.some(vid => vid.evidence_id === state.activeEvidenceId)) {
        dom.selectVideoEvidence.value = state.activeEvidenceId;
      }
    }
  }
}

function updateEvidenceCounts() {
  const total = state.evidence.length;
  const imgCount = state.evidence.filter(e => e.modality === "image").length;
  const audCount = state.evidence.filter(e => e.modality === "audio").length;
  const vidCount = state.evidence.filter(e => e.modality === "video").length;

  dom.sidebarEvidenceCount.textContent = total;
  dom.inventoryCountBadge.textContent = `${total} item${total === 1 ? "" : "s"}`;
  dom.statTotalEvidence.textContent = total;
  dom.statEvidenceMeta.textContent = total > 0 ? `${total} verified custody file${total === 1 ? "" : "s"}` : "No files ingested";
  dom.statImageCount.textContent = imgCount;
  dom.statAudioCount.textContent = audCount;
  dom.statVideoCount.textContent = vidCount;

  if (dom.reportEvidenceSummary) {
    dom.reportEvidenceSummary.textContent = `${total} evidence artifacts ingested (${imgCount} images, ${audCount} audio tracks, ${vidCount} video streams). All hashes verified via SHA-256 integrity check.`;
  }
}

function renderEvidenceInventory() {
  if (!dom.evidenceList) return;

  if (state.evidence.length === 0) {
    dom.evidenceList.innerHTML = `<li class="muted" style="padding:1.5rem; text-align:center;">No evidence files ingested for this case. Drop files in the dropzone above to ingest.</li>`;
    return;
  }

  dom.evidenceList.innerHTML = "";
  state.evidence.forEach(item => {
    const li = document.createElement("li");
    li.className = `evidence-row-item ${item.evidence_id === state.activeEvidenceId ? "active" : ""}`;
    const iconSvg = SVG_ICONS[item.modality] || SVG_ICONS.image;
    const sizeKb = (item.file_size / 1024).toFixed(1);
    const hashShort = item.sha256_hash ? `${item.sha256_hash.substring(0, 8)}…${item.sha256_hash.slice(-6)}` : "Verified";
    const statusClass = item.status === "completed" ? "badge-emerald" : "badge-cobalt";
    const displayName = getEvidenceDisplayName(item);

    const curCase = state.cases.find(c => c.case_id === state.activeCaseId);
    const isLegacy = curCase && (curCase.is_readonly || curCase.case_id === "case_demo_sentinel" || curCase.demo_type === "legacy");

    const deleteBtnHtml = isLegacy ? "" : `
        <button class="btn btn-danger btn-xs btn-delete-artifact" data-eid="${item.evidence_id}" title="Delete Evidence" style="display:inline-flex; align-items:center; justify-content:center; padding:5px 8px; color:#F43F5E; background:rgba(244,63,94,0.1); border:1px solid rgba(244,63,94,0.3); border-radius:5px; cursor:pointer; transition:all 0.15s ease;">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            <line x1="10" y1="11" x2="10" y2="17" />
            <line x1="14" y1="11" x2="14" y2="17" />
          </svg>
        </button>
    `;

    li.innerHTML = `
      <div class="evidence-item-left">
        <div class="evidence-type-icon">${iconSvg}</div>
        <div class="evidence-item-meta">
          <span class="evidence-filename" title="${escapeHtml(item.original_name || item.filename)}">${escapeHtml(displayName)}</span>
          <span class="evidence-sub-meta">
            ${escapeHtml(item.modality.toUpperCase())} · ${sizeKb} KB · SHA-256: <code>${hashShort}</code>
          </span>
        </div>
      </div>
      <div class="evidence-item-right" style="display:flex; align-items:center; gap:8px;">
        <span class="badge ${statusClass} badge-xs">${escapeHtml(item.status || "Ingested")}</span>
        <button class="btn btn-secondary btn-xs btn-open-artifact" data-eid="${item.evidence_id}" title="Inspect & Analyze">
          <span>Analyze</span>
          ${SVG_ICONS.chevronRight}
        </button>
        ${deleteBtnHtml}
      </div>
    `;

    li.querySelector(".btn-open-artifact").addEventListener("click", (e) => {
      e.stopPropagation();
      selectEvidence(item.evidence_id, true);
    });

    const delBtn = li.querySelector(".btn-delete-artifact");
    if (delBtn) {
      delBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteEvidenceItem(item.evidence_id, displayName);
      });
    }

    li.addEventListener("click", () => selectEvidence(item.evidence_id, false));
    dom.evidenceList.appendChild(li);
  });
}

async function deleteEvidenceItem(evidenceId, filename) {
  if (!state.activeCaseId) return;

  const confirmed = window.confirm(
    `Are you sure you want to permanently delete evidence "${filename || evidenceId}"?\n\nThis will remove the file from custody and purge its forensic analysis records.`
  );
  if (!confirmed) return;

  const { ok, status, data } = await apiFetch(
    API.deleteEvidence(state.activeCaseId, evidenceId),
    { method: "DELETE" }
  );

  if (ok) {
    showToast(`Evidence '${filename || evidenceId}' deleted successfully.`, "success");

    if (state.activeEvidenceId === evidenceId) {
      resetEvidenceViews();
    }

    await loadEvidence(state.activeCaseId);
  } else {
    showToast(data.error || `Error ${status}: Failed to delete evidence.`, "error");
  }
}

function resetEvidenceViews() {
  state.activeEvidenceId = null;

  // Clear Image View
  if (dom.evidenceImage) {
    dom.evidenceImage.src = "";
    dom.evidenceImage.style.display = "none";
  }
  if (dom.imageStageBox) dom.imageStageBox.style.display = "none";
  if (dom.imageEmptyPlaceholder) dom.imageEmptyPlaceholder.style.display = "flex";
  if (dom.imageFilenameDisplay) dom.imageFilenameDisplay.textContent = "Image Viewer";
  clearImageAnalysisFindings();

  // Clear Audio View
  if (dom.evidenceAudio) {
    dom.evidenceAudio.src = "";
    dom.evidenceAudio.style.display = "none";
  }
  if (dom.audioEmptyPlaceholder) dom.audioEmptyPlaceholder.style.display = "flex";
  if (dom.audioFilenameDisplay) dom.audioFilenameDisplay.textContent = "Audio Player";
  if (dom.audioMetricsPanel) dom.audioMetricsPanel.style.display = "none";
  clearAudioAnalysisFindings();

  // Clear Video View
  if (dom.evidenceVideo) {
    dom.evidenceVideo.src = "";
    dom.evidenceVideo.style.display = "none";
  }
  if (dom.videoStageBox) dom.videoStageBox.style.display = "none";
  if (dom.videoEmptyPlaceholder) dom.videoEmptyPlaceholder.style.display = "flex";
  if (dom.videoFilenameDisplay) dom.videoFilenameDisplay.textContent = "Surveillance Player";
  if (dom.videoBboxCanvas) {
    const ctx = dom.videoBboxCanvas.getContext("2d");
    ctx.clearRect(0, 0, dom.videoBboxCanvas.width, dom.videoBboxCanvas.height);
  }
  clearVideoAnalysisFindings();
}

function renderOverviewEvidenceStrip() {
  if (!dom.overviewEvidenceGrid) return;

  if (state.evidence.length === 0) {
    dom.overviewEvidenceEmpty.style.display = "block";
    dom.overviewEvidenceGrid.style.display = "none";
    return;
  }

  dom.overviewEvidenceEmpty.style.display = "none";
  dom.overviewEvidenceGrid.style.display = "grid";
  dom.overviewEvidenceGrid.innerHTML = "";

  const recent = state.evidence.slice(0, 4);
  recent.forEach(item => {
    const card = document.createElement("div");
    card.className = "metric-card";
    card.style.cursor = "pointer";
    const iconSvg = SVG_ICONS[item.modality] || SVG_ICONS.image;
    const displayName = getEvidenceDisplayName(item);
    card.innerHTML = `
      <div class="metric-icon metric-icon--blue">${iconSvg}</div>
      <div class="metric-body">
        <span class="metric-label">${item.modality.toUpperCase()}</span>
        <span class="metric-value" title="${escapeHtml(displayName)}" style="font-size:13px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:180px;">${escapeHtml(displayName)}</span>
        <span class="metric-meta">${item.status || "Ready"}</span>
      </div>
    `;
    card.addEventListener("click", () => selectEvidence(item.evidence_id, true));
    dom.overviewEvidenceGrid.appendChild(card);
  });
}

function selectEvidence(evidenceId, jumpToModality = false) {
  state.activeEvidenceId = evidenceId;
  const item = state.evidence.find(e => e.evidence_id === evidenceId);
  if (!item) return;

  // Highlight in inventory
  document.querySelectorAll(".evidence-row-item").forEach(el => {
    const isCurrent = el.querySelector(`.btn-open-artifact[data-eid="${evidenceId}"]`);
    el.classList.toggle("active", Boolean(isCurrent));
  });

  const cacheBust = item.sha256 ? item.sha256.substring(0, 12) : Date.now();
  const fileUrl = `${API.evidenceFile(state.activeCaseId, evidenceId)}?v=${cacheBust}`;
  const displayName = getEvidenceDisplayName(item);

  if (item.modality === "image") {
    if (dom.selectImageEvidence) dom.selectImageEvidence.value = evidenceId;
    dom.imageFilenameDisplay.textContent = displayName;
    dom.imageFilenameDisplay.title = item.original_name || item.filename;
    dom.evidenceImage.src = fileUrl;
    if (dom.imageStageBox) dom.imageStageBox.style.display = "inline-flex";
    dom.evidenceImage.style.display = "block";
    dom.imageEmptyPlaceholder.style.display = "none";
    dom.bboxCanvas.style.display = "block";

    const applyImageFindings = () => {
      let analysisData = item.analysis_json;
      if (typeof analysisData === "string") {
        try { analysisData = JSON.parse(analysisData); } catch (e) {}
      }
      if (analysisData) {
        if (dom.imageStatusBadge) {
          const st = item.analysis_status || analysisData.status || "completed";
          if (st === "partial") {
            dom.imageStatusBadge.textContent = "Analysis Partial";
            dom.imageStatusBadge.className = "badge badge-amber badge-sm";
          } else if (st === "failed") {
            dom.imageStatusBadge.textContent = "Analysis Failed";
            dom.imageStatusBadge.className = "badge badge-crimson badge-sm";
          } else {
            dom.imageStatusBadge.textContent = "Analysis Complete";
            dom.imageStatusBadge.className = "badge badge-emerald badge-sm";
          }
        }
        renderImageAnalysisFindings(analysisData);
        drawBoundingBoxes(analysisData);
      } else {
        clearImageAnalysisFindings();
        if (dom.imageStatusBadge) {
          const isFailed = item.analysis_status === "failed";
          const isPartial = item.analysis_status === "partial";
          const isAnalyzing = item.analysis_status === "analyzing";
          if (isFailed) {
            dom.imageStatusBadge.textContent = "Analysis Failed";
            dom.imageStatusBadge.className = "badge badge-crimson badge-sm";
          } else if (isPartial) {
            dom.imageStatusBadge.textContent = "Analysis Partial";
            dom.imageStatusBadge.className = "badge badge-amber badge-sm";
          } else if (isAnalyzing) {
            dom.imageStatusBadge.textContent = "Analyzing…";
            dom.imageStatusBadge.className = "badge badge-amber badge-sm";
          } else {
            dom.imageStatusBadge.textContent = "Ready";
            dom.imageStatusBadge.className = "badge badge-cobalt badge-sm";
          }
        }
      }
    };

    dom.evidenceImage.onload = applyImageFindings;
    if (dom.evidenceImage.complete && dom.evidenceImage.naturalWidth > 0) {
      applyImageFindings();
    }
    if (jumpToModality) switchView("image");
  } else if (item.modality === "audio") {
    if (dom.selectAudioEvidence) dom.selectAudioEvidence.value = evidenceId;
    dom.audioFilenameDisplay.textContent = displayName;
    dom.audioFilenameDisplay.title = item.original_name || item.filename;
    dom.evidenceAudio.src = fileUrl;
    dom.evidenceAudio.style.display = "block";
    dom.audioEmptyPlaceholder.style.display = "none";
    // Set Chain of custody and Evidence Details metadata
    if (dom.audioCustodyEid) dom.audioCustodyEid.textContent = item.evidence_id || "—";
    if (dom.audioCustodyCase) dom.audioCustodyCase.textContent = item.case_id || state.activeCaseId || "—";
    if (dom.audioCustodyFilename) dom.audioCustodyFilename.textContent = item.original_name || item.filename || "—";
    if (dom.audioCustodyHash) dom.audioCustodyHash.textContent = item.sha256_hash || "—";
    if (dom.audioDetailFormat) dom.audioDetailFormat.textContent = item.mime_type || "audio/mpeg";
    if (dom.audioDetailFilesize) dom.audioDetailFilesize.textContent = item.file_size ? `${(item.file_size / 1024).toFixed(1)} KB` : "—";
    if (dom.audioDetailUploaded) dom.audioDetailUploaded.textContent = item.uploaded_at ? new Date(item.uploaded_at).toLocaleString() : "—";

    // Update HTML audio player metadata when loaded
    dom.evidenceAudio.onloadedmetadata = () => {
      if (dom.audioStatDuration && (!item.analysis_json || dom.audioStatDuration.textContent === "—")) {
        dom.audioStatDuration.textContent = `${dom.evidenceAudio.duration.toFixed(1)}s`;
      }
    };

    if (item.analysis_json) {
      renderAudioAnalysisFindings(item.analysis_json);
    } else {
      clearAudioAnalysisFindings();
      if (item.analysis_status === "analyzing") {
        if (dom.audioStatusBadge) {
          dom.audioStatusBadge.textContent = "Transcribing…";
          dom.audioStatusBadge.className = "badge badge-amber badge-sm";
        }
        if (dom.audioStatStatus) dom.audioStatStatus.textContent = "Transcribing…";
      } else if (item.analysis_status === "failed") {
        if (dom.audioStatusBadge) {
          dom.audioStatusBadge.textContent = "Transcription Failed";
          dom.audioStatusBadge.className = "badge badge-crimson badge-sm";
        }
        if (dom.audioStatStatus) dom.audioStatStatus.textContent = "Failed";
      }
    }
    if (jumpToModality) switchView("audio");
  } else if (item.modality === "video") {
    if (dom.selectVideoEvidence) dom.selectVideoEvidence.value = evidenceId;
    dom.videoFilenameDisplay.textContent = displayName;
    dom.videoFilenameDisplay.title = item.original_name || item.filename;
    dom.evidenceVideo.src = fileUrl;
    if (dom.videoStageBox) dom.videoStageBox.style.display = "inline-flex";
    dom.evidenceVideo.style.display = "block";
    if (dom.videoBboxCanvas) dom.videoBboxCanvas.style.display = "block";
    dom.videoEmptyPlaceholder.style.display = "none";

    dom.evidenceVideo.onloadedmetadata = () => {
      if (item.analysis_json) {
        updateVideoOverlay();
      }
    };

    if (item.analysis_json) {
      state.currentVideoAnalysis = item.analysis_json;
      renderVideoAnalysisFindings(item.analysis_json);
      updateVideoOverlay();
    } else {
      clearVideoAnalysisFindings();
      if (item.analysis_status === "analyzing") {
        if (dom.videoStatusBadge) {
          dom.videoStatusBadge.textContent = "Analyzing…";
          dom.videoStatusBadge.className = "badge badge-amber badge-sm";
        }
      } else if (item.analysis_status === "partial") {
        if (dom.videoStatusBadge) {
          dom.videoStatusBadge.textContent = "Analysis Partial";
          dom.videoStatusBadge.className = "badge badge-amber badge-sm";
        }
      } else if (item.analysis_status === "failed") {
        if (dom.videoStatusBadge) {
          dom.videoStatusBadge.textContent = "Analysis Failed";
          dom.videoStatusBadge.className = "badge badge-crimson badge-sm";
        }
      } else {
        if (dom.videoStatusBadge) {
          dom.videoStatusBadge.textContent = "Ready";
          dom.videoStatusBadge.className = "badge badge-neutral badge-sm";
        }
      }
    }
    if (jumpToModality) switchView("video");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   DRAG AND DROP EVIDENCE INGESTION
════════════════════════════════════════════════════════════════════════════ */
function initDragDrop() {
  const zone = dom.uploadZone;
  const input = dom.fileInput;
  if (!zone || !input) return;

  ["dragenter", "dragover"].forEach(evt => {
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(evt => {
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
    });
  });

  zone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) uploadFile(files[0]);
  });

  input.addEventListener("change", () => {
    if (input.files.length > 0) uploadFile(input.files[0]);
  });
}

async function uploadFile(file) {
  if (!state.activeCaseId) {
    showToast("Please select an active case container before uploading.", "warning");
    return;
  }

  const curCase = state.cases.find(c => c.case_id === state.activeCaseId);
  if (curCase && (curCase.is_readonly || curCase.case_id === "case_demo_sentinel" || curCase.demo_type === "legacy")) {
    showToast("The selected case is a read-only reference demonstration case. Please switch to your writable live-demo workspace or create a new case to upload evidence.", "warning");
    if (dom.uploadStatus) {
      dom.uploadStatus.textContent = "Upload blocked: Legacy demo case is read-only. Switch to a writable live-demo case.";
    }
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  const csrf = getCsrfToken();
  if (csrf) {
    formData.append("csrf_token", csrf);
  }

  dom.uploadStatus.innerHTML = `<span class="spin-loader"></span> Ingesting and calculating SHA-256 hash…`;

  try {
    const { ok, status, data } = await apiFetch(API.evidence(state.activeCaseId), {
      method: "POST",
      body: formData,
      silent403: true,
    });

    if (ok) {
      showToast(`Artifact '${file.name}' ingested with verified SHA-256 hash.`, "success");
      dom.uploadStatus.textContent = "";
      dom.fileInput.value = "";
      await loadEvidence(state.activeCaseId);
      if (data && data.evidence && data.evidence.evidence_id) {
        selectEvidence(data.evidence.evidence_id, true);
      }
    } else {
      const msg = (data && data.error) || "Upload failed.";
      dom.uploadStatus.textContent = msg;
      showToast(msg, "error");
    }
  } catch (err) {
    dom.uploadStatus.textContent = `Upload failed: ${err.message}`;
    showToast(`Network error: ${err.message}`, "error");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   IMAGE ANALYSIS & BOUNDING BOXES
══════════════════════════════════════════════════════════════════════════ */
async function runImageAnalysis() {
  if (!state.activeCaseId) {
    showToast("Please select a case first.", "warning");
    return;
  }

  // Ensure an image evidence item is selected
  let ev = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
  if (!ev || ev.modality !== "image") {
    const firstImg = state.evidence.find(e => e.modality === "image");
    if (firstImg) {
      selectEvidence(firstImg.evidence_id, false);
      ev = firstImg;
    }
  }

  if (!ev || ev.modality !== "image" || !state.activeEvidenceId) {
    showToast("Please select an image artifact from the Evidence Library.", "warning");
    return;
  }

  if (dom.btnRunImageAnalysis) dom.btnRunImageAnalysis.disabled = true;
  if (dom.imageStatusBadge) {
    dom.imageStatusBadge.textContent = "Analyzing…";
    dom.imageStatusBadge.className = "badge badge-amber badge-sm";
  }

  try {
    const { ok, status, data } = await apiFetch(
      API.analyzeImage(state.activeCaseId, state.activeEvidenceId),
      { method: "POST" }
    );

    if (ok && data) {
      let analysisData = data.analysis;
      if (typeof analysisData === "string") {
        try { analysisData = JSON.parse(analysisData); } catch (e) {}
      }

      const backendStatus = data.status || (analysisData && analysisData.status) || "completed";
      const cur = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);

      if (backendStatus === "failed") {
        const errorMsg =
          (data && data.error) ||
          (analysisData && analysisData.error) ||
          (analysisData && analysisData.detection && analysisData.detection.error) ||
          "Live neural inference could not complete on this host.";

        if (dom.imageStatusBadge) {
          dom.imageStatusBadge.textContent = "Inference Unavailable";
          dom.imageStatusBadge.className = "badge badge-crimson badge-sm";
          dom.imageStatusBadge.title = errorMsg;
        }
        if (cur) cur.analysis_status = "failed";
        showToast(errorMsg, "error", 6000);
        renderInferenceFailureUI(errorMsg, analysisData);
      } else if (backendStatus === "partial") {
        if (dom.imageStatusBadge) {
          dom.imageStatusBadge.textContent = "Analysis Partial";
          dom.imageStatusBadge.className = "badge badge-amber badge-sm";
        }
        if (cur) {
          cur.analysis_json = analysisData;
          cur.analysis_status = "partial";
        }
        showToast("Image analysis completed with partial submodel results.", "warning");
        renderImageAnalysisFindings(analysisData);
        drawBoundingBoxes(analysisData);
      } else {
        if (dom.imageStatusBadge) {
          dom.imageStatusBadge.textContent = "Live Neural Output";
          dom.imageStatusBadge.className = "badge badge-emerald badge-sm";
        }
        if (cur) {
          cur.analysis_json = analysisData;
          cur.analysis_status = "completed";
        }
        showToast("RT-DETR live visual analysis executed successfully.", "success");
        renderImageAnalysisFindings(analysisData);
        drawBoundingBoxes(analysisData);
      }
    } else {
      const errorMsg =
        (data && data.error) ||
        `Error ${status}: Live inference unavailable on this deployment.`;
      const cur = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
      if (cur) cur.analysis_status = "failed";
      if (dom.imageStatusBadge) {
        dom.imageStatusBadge.textContent = "Inference Unavailable";
        dom.imageStatusBadge.className = "badge badge-crimson badge-sm";
        dom.imageStatusBadge.title = errorMsg;
      }
      showToast(errorMsg, "error", 6000);
      renderInferenceFailureUI(errorMsg, null);
    }
  } catch (err) {
    const cur = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
    if (cur) cur.analysis_status = "failed";
    if (dom.imageStatusBadge) {
      dom.imageStatusBadge.textContent = "Inference Unavailable";
      dom.imageStatusBadge.className = "badge badge-crimson badge-sm";
      dom.imageStatusBadge.title = err.message;
    }
    showToast(`Analysis request failed: ${err.message}`, "error", 6000);
    renderInferenceFailureUI(`Analysis request failed: ${err.message}`, null);
  } finally {
    if (dom.btnRunImageAnalysis) dom.btnRunImageAnalysis.disabled = false;
  }
}

function renderInferenceFailureUI(errorMsg, analysisData) {
  if (dom.imgAiSceneSummaryContent) {
    dom.imgAiSceneSummaryContent.innerHTML = `
      <div class="provenance-banner provenance-banner--failed" style="padding:12px; background:rgba(239, 68, 68, 0.08); border-left:3px solid #EF4444; border-radius:0 6px 6px 0;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <span class="badge badge-crimson badge-xs" style="font-weight:700;">LIVE INFERENCE UNAVAILABLE</span>
          <button class="btn btn-secondary btn-xs btn-restore-sample" id="btn-restore-sample-summary" style="font-size:11px; padding:3px 8px;">
            Restore Sample Baseline
          </button>
        </div>
        <p style="font-size:12.5px; color:var(--text-primary); margin:0 0 6px 0; line-height:1.45;">
          ${escapeHtml(errorMsg)}
        </p>
        <p style="font-size:11.5px; color:var(--text-muted); margin:0; line-height:1.4;">
          The cloud runtime cannot run heavy neural weights (RT-DETR/CLIP/BLIP) under host limits (e.g. Render 512MB RAM or 30s worker timeout). Run locally for full live CPU/GPU execution.
        </p>
      </div>
    `;
    const btn = document.getElementById("btn-restore-sample-summary");
    if (btn) btn.addEventListener("click", restoreSampleBaseline);
  }

  if (dom.rtdetrContent) {
    dom.rtdetrContent.innerHTML = `
      <div style="padding:12px; background:rgba(239,68,68,0.05); border:1px dashed rgba(239,68,68,0.25); border-radius:6px; text-align:center;">
        <p style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">
          Live object detection could not be computed on this host.
        </p>
        <button class="btn btn-secondary btn-xs btn-restore-sample" id="btn-restore-sample-rtdetr">
          View Precomputed Sample Baseline (8 objects)
        </button>
      </div>
    `;
    const btn2 = document.getElementById("btn-restore-sample-rtdetr");
    if (btn2) btn2.addEventListener("click", restoreSampleBaseline);
  }
}

async function restoreSampleBaseline() {
  if (!state.activeCaseId || !state.activeEvidenceId) return;
  try {
    const { ok, data } = await apiFetch(API.restoreSeededSample(state.activeCaseId, state.activeEvidenceId), { method: "POST" });
    if (ok && data && data.analysis) {
      let analysisData = data.analysis;
      if (typeof analysisData === "string") {
        try { analysisData = JSON.parse(analysisData); } catch (e) {}
      }
      const cur = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
      if (cur) {
        cur.analysis_json = analysisData;
        cur.analysis_status = "completed";
        if (cur.modality === "audio") {
          renderAudioAnalysisFindings(analysisData);
          if (dom.audioStatusBadge) {
            dom.audioStatusBadge.textContent = "Baseline Restored";
            dom.audioStatusBadge.className = "badge badge-emerald badge-sm";
          }
        } else if (cur.modality === "video") {
          renderVideoAnalysisFindings(analysisData);
          if (dom.videoStatusBadge) {
            dom.videoStatusBadge.textContent = "Baseline Restored";
            dom.videoStatusBadge.className = "badge badge-emerald badge-sm";
          }
        } else {
          renderImageAnalysisFindings(analysisData);
          drawBoundingBoxes(analysisData);
          if (dom.imageStatusBadge) {
            dom.imageStatusBadge.textContent = "Baseline Restored";
            dom.imageStatusBadge.className = "badge badge-emerald badge-sm";
          }
        }
      }
      showToast("Restored precomputed baseline sample data.", "info");
    } else {
      showToast((data && data.error) || "Could not restore sample data.", "error");
    }
  } catch (err) {
    showToast(`Failed to restore sample: ${err.message}`, "error");
  }
}

function synthesizeClientSideImageSummaries(analysis) {
  const objects = (analysis.detection && analysis.detection.objects) || (analysis.rtdetr && analysis.rtdetr.objects) || [];
  const caption = (analysis.caption && analysis.caption.caption) || (analysis.blip && analysis.blip.caption) || "";
  const clipMatches = (analysis.clip && analysis.clip.matches) || [];
  const topScene = clipMatches.length > 0 ? clipMatches[0].label : "unspecified scene";

  const personLabels = new Set(["person", "pedestrian", "man", "woman", "child"]);
  const vehicleLabels = new Set(["car", "truck", "bus", "motorcycle", "bicycle", "vehicle", "van", "train", "motorbike"]);
  const weaponLabels = new Set(["gun", "knife", "pistol", "rifle", "weapon", "firearm"]);

  let persons = 0, vehicles = 0, weapons = 0, other = 0;
  objects.forEach(obj => {
    const lbl = (obj.label || "").toLowerCase();
    if (personLabels.has(lbl)) persons++;
    else if (vehicleLabels.has(lbl)) vehicles++;
    else if (weaponLabels.has(lbl)) weapons++;
    else other++;
  });

  const stats = {
    total_objects: objects.length,
    persons: persons,
    vehicles: vehicles,
    weapons: weapons,
    other_objects: other,
    scene_type: topScene,
  };

  const sceneSummary = caption
    ? `Forensic visual analysis identifies ${caption} within a ${topScene} environment. RT-DETR localized ${objects.length} entity instances with high geometric confidence.`
    : `Visual analysis localized ${objects.length} entities in a ${topScene} setting.`;

  const visualSummary = {
    visible_scene: `Scene classified as ${topScene} based on zero-shot visual semantics.`,
    spatial_entities: `Localized ${persons} person(s), ${vehicles} vehicle(s), ${weapons} weapon/risk entity(ies), and ${other} additional item(s).`,
    uncertainty_boundary: "Static two-dimensional image. Hidden angles, occlusion, and lighting variations limit peripheral verification."
  };

  const actions = [];
  objects.filter(o => personLabels.has((o.label || "").toLowerCase())).forEach((p, idx) => {
    const box = p.box_pixels || [0, 0, 10, 10];
    const h = Math.abs(box[3] - box[1]);
    const w = Math.max(1, Math.abs(box[2] - box[0]));
    const ratio = h / w;
    const pose = ratio >= 1.6 ? "Upright / standing / walking posture" : "Low-profile, seated, or partially occluded posture";
    actions.push({
      person_index: idx + 1,
      observable_pose: pose,
      confidence: p.confidence,
      forensic_notice: "Observable physical posture only. Static imagery cannot confirm movement or intent."
    });
  });

  const facts = objects.map((obj, i) => {
    const lbl = (obj.label || "object").toLowerCase();
    let cat = "Other Object";
    if (personLabels.has(lbl)) cat = "Person";
    else if (vehicleLabels.has(lbl)) cat = "Vehicle";
    else if (weaponLabels.has(lbl)) cat = "Weapon / Risk";
    return {
      entity_id: `obj_${i+1}`,
      label: obj.label,
      category: cat,
      confidence: obj.confidence,
      box_pixels: obj.box_pixels || [],
      box_normalized: obj.box_normalized || [],
    };
  });

  const scenarios = [
    {
      hypothesis: `Active presence in ${topScene}`,
      details: `Presence of ${persons} person(s) and ${vehicles} vehicle(s) indicates potential transit or gathering in a ${topScene} setting.`,
      disclaimer: "Unverified working hypothesis. Requires independent corroboration."
    },
    {
      hypothesis: "Forensic Entity Proximity Analysis",
      details: `Spatial cluster of ${objects.length} localized items. Cross-reference with physical evidence or temporal video feeds.`,
      disclaimer: "AI-generated investigative theory. Not legal proof."
    },
    {
      hypothesis: "Environmental Context Assessment",
      details: `CLIP semantic alignment (${topScene}). Recommended to verify geographical location, weather, and lighting logs.`,
      disclaimer: "Investigative scenario only. Human verification mandatory."
    }
  ];

  return {
    statistics: stats,
    scene_summary: sceneSummary,
    visual_summary: visualSummary,
    actions_detected: actions,
    evidence_facts: facts,
    application_scenarios: scenarios,
  };
}

function renderImageAnalysisFindings(analysis) {
  if (!analysis) return;

  const synth = (analysis.statistics && analysis.scene_summary)
    ? analysis
    : synthesizeClientSideImageSummaries(analysis);

  const isSeededSample =
    analysis.is_seeded_sample === true ||
    analysis.result_source === "precomputed_demo_result" ||
    (analysis.provenance && (
      analysis.provenance.result_source === "precomputed_demo_result" ||
      analysis.provenance.is_demo === true ||
      analysis.provenance === "Verified Forensic Baseline (PekingU/rtdetr_r50vd)"
    ));

  if (dom.imageStatusBadge) {
    if (isSeededSample) {
      dom.imageStatusBadge.textContent = "Seeded Sample Baseline";
      dom.imageStatusBadge.className = "badge badge-cobalt badge-sm";
      dom.imageStatusBadge.title = "Precomputed forensic baseline detections. Click 'Run Image Analysis' to execute live on host.";
    } else if (analysis.status === "completed") {
      dom.imageStatusBadge.textContent = "Live Neural Output";
      dom.imageStatusBadge.className = "badge badge-emerald badge-sm";
      dom.imageStatusBadge.title = "Live neural network forward pass executed on host.";
    } else if (analysis.status === "partial") {
      dom.imageStatusBadge.textContent = "Partial Inference";
      dom.imageStatusBadge.className = "badge badge-amber badge-sm";
    }
  }

  // 1. Statistics Strip
  const stats = synth.statistics || {};
  const rawObjects =
    (analysis.detection && analysis.detection.objects) ||
    (analysis.rtdetr && analysis.rtdetr.objects) ||
    (analysis.evidence_facts && Array.isArray(analysis.evidence_facts.items) && analysis.evidence_facts.items) ||
    [];

  const total = stats.total_detections != null
    ? stats.total_detections
    : (stats.total_objects != null ? stats.total_objects : rawObjects.length);
  const persons = stats.persons_detected != null
    ? stats.persons_detected
    : (stats.persons != null ? stats.persons : 0);
  const vehicles = stats.vehicles_detected != null
    ? stats.vehicles_detected
    : (stats.vehicles != null ? stats.vehicles : 0);
  const weapons = stats.weapons_detected != null
    ? stats.weapons_detected
    : (stats.weapons != null ? stats.weapons : 0);
  const scene = stats.primary_scene_type || stats.scene_type || "—";

  if (dom.imgStatTotal) dom.imgStatTotal.textContent = total;
  if (dom.imgStatPersons) dom.imgStatPersons.textContent = persons;
  if (dom.imgStatVehicles) dom.imgStatVehicles.textContent = vehicles;
  if (dom.imgStatWeapons) dom.imgStatWeapons.textContent = weapons;
  if (dom.imgStatScene) dom.imgStatScene.textContent = scene;

  // 2. AI Scene Summary
  if (dom.imgAiSceneSummaryContent) {
    const summaryText = synth.scene_summary || "Scene summary pending.";
    let bannerHtml = "";
    if (isSeededSample) {
      bannerHtml = `
        <div style="margin-bottom:8px; padding:6px 10px; background:rgba(56, 189, 248, 0.08); border-left:3px solid var(--cyan-primary); border-radius:0 4px 4px 0; display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:11px; font-weight:700; color:var(--cyan-primary); letter-spacing:0.04em;">PROVENANCE: SEEDED SAMPLE BASELINE</span>
          <span style="font-size:10.5px; color:var(--text-muted);">Precomputed Demo Data</span>
        </div>
      `;
    } else if (analysis.result_source === "fresh_inference") {
      const dur = analysis.provenance?.inference_duration_ms ? `${analysis.provenance.inference_duration_ms}ms` : "Live Host";
      bannerHtml = `
        <div style="margin-bottom:8px; padding:6px 10px; background:rgba(16, 185, 129, 0.08); border-left:3px solid #10B981; border-radius:0 4px 4px 0; display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:11px; font-weight:700; color:#34D399; letter-spacing:0.04em;">PROVENANCE: LIVE NEURAL INFERENCE (RT-DETR)</span>
          <span style="font-size:10.5px; color:var(--text-muted);">${dur}</span>
        </div>
      `;
    }

    dom.imgAiSceneSummaryContent.innerHTML = `
      ${bannerHtml}
      <div style="font-size:13px; line-height:1.55; color:var(--text-primary); border-left:3px solid var(--cyan-primary); padding-left:10px;">
        ${escapeHtml(summaryText)}
      </div>
    `;
  }

  // 3. Visual Summary
  if (dom.imgVisualSummaryContent) {
    const vs = synth.visual_summary || {};
    let directObs = "";
    if (Array.isArray(vs.direct_observations)) {
      directObs = vs.direct_observations.map(d => `• ${escapeHtml(d)}`).join("<br/>");
    } else {
      directObs = escapeHtml(vs.direct_observations || vs.visible_scene || "Analysis pending.");
    }

    let spatialDist = "";
    if (Array.isArray(vs.spatial_distribution)) {
      spatialDist = vs.spatial_distribution.map(d => `• ${escapeHtml(d)}`).join("<br/>");
    } else {
      spatialDist = escapeHtml(vs.spatial_distribution || vs.spatial_entities || "No spatial distribution computed.");
    }

    const uncert = escapeHtml(vs.uncertainty_boundaries || vs.uncertainty_boundary || "Two-dimensional imagery limit.");

    dom.imgVisualSummaryContent.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:8px;">
        <div>
          <span style="font-size:11px; font-weight:600; color:var(--cyan-primary); text-transform:uppercase; letter-spacing:0.04em;">Direct Scene Observations:</span>
          <p style="font-size:12.5px; color:var(--text-primary); margin-top:2px; line-height:1.5;">${directObs}</p>
        </div>
        <div>
          <span style="font-size:11px; font-weight:600; color:#38BDF8; text-transform:uppercase; letter-spacing:0.04em;">Spatial Distribution:</span>
          <p style="font-size:12px; color:var(--text-secondary); margin-top:2px; line-height:1.5;">${spatialDist}</p>
        </div>
        <div style="padding:6px 8px; background:rgba(255,255,255,0.02); border-radius:4px;">
          <span style="font-size:10.5px; font-weight:600; color:var(--text-muted); text-transform:uppercase;">Forensic Limitations & Uncertainty Boundary:</span>
          <p style="font-size:11.5px; color:var(--text-muted); margin-top:2px; font-style:italic;">${uncert}</p>
        </div>
      </div>
    `;
  }

  // 4. Actions Detected
  if (dom.imgActionsDetectedContent) {
    let actionsList = [];
    let notice = "Static 2D imagery does not support temporal action recognition. Observable poses reflect physical geometric orientation only and must never be interpreted as intent or criminal conduct.";

    if (Array.isArray(synth.actions_detected)) {
      actionsList = synth.actions_detected;
    } else if (synth.actions_detected && typeof synth.actions_detected === "object") {
      if (synth.actions_detected.forensic_notice) {
        notice = synth.actions_detected.forensic_notice;
      }
      const rawPostures = synth.actions_detected.observed_postures || [];
      actionsList = rawPostures.map((p, idx) => {
        if (typeof p === "object") return p;
        return {
          person_index: idx + 1,
          observable_pose: p,
          confidence: 0.9,
          forensic_notice: "Observable physical posture only."
        };
      });
    }

    let actHtml = `
      <div style="margin-bottom:8px; padding:6px 8px; background:rgba(245, 158, 11, 0.08); border-left:3px solid #F59E0B; border-radius:0 4px 4px 0;">
        <span style="font-size:11px; font-weight:600; color:#FBBF24;">FORENSIC NOTICE:</span>
        <span style="font-size:11px; color:var(--text-secondary);"> ${escapeHtml(notice)}</span>
      </div>
    `;
    if (actionsList.length === 0) {
      actHtml += `<p class="muted" style="font-size:12px;">No human entities detected in current evidence frame.</p>`;
    } else {
      actionsList.forEach((a, idx) => {
        const poseText = typeof a === "string" ? a : (a.observable_pose || "Neutral posture");
        const personNum = a.person_index || (idx + 1);
        const cert = a.confidence ? `${Math.round(a.confidence * 100)}% pose cert` : "Assessed";
        actHtml += `
          <div class="posture-item-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-weight:600; color:var(--text-primary); font-size:12px;">Person #${personNum}: ${escapeHtml(poseText)}</span>
              <span class="badge badge-emerald badge-xs">${escapeHtml(cert)}</span>
            </div>
            ${a.forensic_notice ? `<div style="font-size:11px; color:var(--text-muted); margin-top:3px;">${escapeHtml(a.forensic_notice)}</div>` : ""}
          </div>
        `;
      });
    }
    dom.imgActionsDetectedContent.innerHTML = actHtml;
  }

  // 5. Evidence Facts Table
  let factsList = [];
  if (Array.isArray(synth.evidence_facts)) {
    factsList = synth.evidence_facts;
  } else if (synth.evidence_facts && Array.isArray(synth.evidence_facts.items)) {
    factsList = synth.evidence_facts.items;
  } else if (analysis.detection && Array.isArray(analysis.detection.objects)) {
    factsList = analysis.detection.objects;
  } else if (analysis.rtdetr && Array.isArray(analysis.rtdetr.objects)) {
    factsList = analysis.rtdetr.objects;
  }

  if (dom.imgFactsCountBadge) {
    dom.imgFactsCountBadge.textContent = `${factsList.length} item${factsList.length === 1 ? "" : "s"}`;
  }
  if (dom.imgFactsTableContainer) {
    const ev = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
    const hash = ev ? (ev.sha256 ? ev.sha256.substring(0, 16) + "…" : (ev.sha256_hash ? ev.sha256_hash.substring(0, 16) + "…" : "Verified")) : "Verified";
    let tblHtml = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; font-size:11px; color:var(--text-muted);">
        <span>Custody: <code>${escapeHtml(state.activeEvidenceId || "")}</code></span>
        <span>SHA-256: <code>${escapeHtml(hash)}</code></span>
      </div>
      <table class="forensic-facts-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Entity Class</th>
            <th>Category</th>
            <th>Confidence</th>
            <th>Coordinates [x1, y1, x2, y2]</th>
          </tr>
        </thead>
        <tbody>
    `;
    if (factsList.length === 0) {
      tblHtml += `<tr><td colspan="5" class="muted" style="text-align:center; padding:12px;">No entities localized above confidence threshold.</td></tr>`;
    } else {
      factsList.forEach((f, idx) => {
        const confVal = f.confidence != null ? f.confidence : (f.confidence_pct != null ? f.confidence_pct / 100 : 0.9);
        const confPct = Math.round(confVal * 100);
        const cat = (f.category || (f.label === "person" ? "Person" : "Object")).toLowerCase();
        const badgeColor = cat.includes("person") ? "badge-cyan" : (cat.includes("vehicle") ? "badge-cobalt" : (cat.includes("weapon") ? "badge-crimson" : "badge-slate"));
        const coords = (f.box_pixels && f.box_pixels.length === 4)
          ? `[${f.box_pixels.map(v => Math.round(v)).join(", ")}]`
          : (f.box_normalized ? `[${f.box_normalized.map(v => Number(v).toFixed(2)).join(", ")}]` : "—");
        tblHtml += `
          <tr>
            <td style="color:var(--text-muted);">${idx + 1}</td>
            <td style="font-weight:600; color:var(--text-primary); text-transform:capitalize;">${escapeHtml(f.label || "Entity")}</td>
            <td><span class="badge ${badgeColor} badge-xs">${escapeHtml(f.category || "Entity")}</span></td>
            <td><span class="badge badge-emerald badge-xs">${confPct}%</span></td>
            <td><code style="font-size:10.5px;">${escapeHtml(coords)}</code></td>
          </tr>
        `;
      });
    }
    tblHtml += `</tbody></table>`;
    dom.imgFactsTableContainer.innerHTML = tblHtml;
  }

  // 6. Investigative Scenarios
  let scenariosList = [];
  let scNotice = "The following scenarios represent automated AI working hypotheses designed exclusively to assist investigative planning. They are NOT certified facts, do not establish legal liability, and require independent verification, physical corroboration, and human detective oversight.";

  if (Array.isArray(synth.application_scenarios)) {
    scenariosList = synth.application_scenarios;
  } else if (synth.application_scenarios && typeof synth.application_scenarios === "object") {
    if (synth.application_scenarios.notice) {
      scNotice = synth.application_scenarios.notice;
    }
    scenariosList = synth.application_scenarios.scenarios || [];
  }

  if (dom.imgScenariosContent) {
    let scenHtml = `
      <div style="margin-bottom:10px; padding:8px 10px; background:rgba(239, 68, 68, 0.08); border-left:3px solid #EF4444; border-radius:0 4px 4px 0;">
        <span style="font-weight:700; color:#F87171; font-size:11px;">MANDATORY FORENSIC DISCLAIMER:</span>
        <p style="font-size:11px; color:var(--text-secondary); margin-top:2px;">
          ${escapeHtml(scNotice)}
        </p>
      </div>
    `;
    if (scenariosList.length === 0) {
      scenHtml += `<p class="muted" style="padding:0.5rem 0;">No application scenarios synthesized for this scene.</p>`;
    } else {
      scenariosList.forEach(sc => {
        const title = sc.title || sc.hypothesis || "Hypothesis";
        const details = sc.description || sc.details || "";
        const disclaimer = sc.verification_status || sc.disclaimer || "Unverified working hypothesis";
        scenHtml += `
          <div class="scenario-card-item">
            <div class="scenario-title">💡 ${escapeHtml(title)}</div>
            <div style="color:var(--text-secondary); font-size:12px; line-height:1.45;">${escapeHtml(details)}</div>
            <div style="margin-top:6px; font-size:10.5px; color:#F59E0B; font-style:italic;">⚠️ ${escapeHtml(disclaimer)}</div>
          </div>
        `;
      });
    }
    dom.imgScenariosContent.innerHTML = scenHtml;
  }

  // RT-DETR Detections
  const rtdetr = analysis.detection || analysis.rtdetr || {};
  const rtdetrStatus = (analysis.submodel_statuses && analysis.submodel_statuses.rtdetr) || rtdetr.status || "completed";
  const objects = rtdetr.objects || [];

  if (dom.rtdetrCountBadge) {
    dom.rtdetrCountBadge.style.display = "inline-flex";
    if (rtdetrStatus === "failed" || rtdetrStatus === "unavailable") {
      dom.rtdetrCountBadge.textContent = "Failed";
      dom.rtdetrCountBadge.className = "badge badge-crimson badge-xs";
    } else {
      dom.rtdetrCountBadge.textContent = `${objects.length} object${objects.length === 1 ? "" : "s"}`;
      dom.rtdetrCountBadge.className = "badge badge-emerald badge-xs";
    }
  }

  if (dom.rtdetrContent) {
    if (rtdetrStatus === "failed" || rtdetrStatus === "unavailable") {
      dom.rtdetrContent.innerHTML = `<p class="muted" style="color:var(--crimson);">RT-DETR detection unavailable: ${escapeHtml(rtdetr.error || 'Submodel execution error')}</p>`;
    } else if (objects.length === 0) {
      dom.rtdetrContent.innerHTML = `<p class="muted">No objects localized above confidence threshold.</p>`;
    } else {
      let rows = `<div style="display:flex; flex-direction:column; gap:6px;">`;
      objects.forEach(obj => {
        const confPct = Math.round(obj.confidence * 100);
        rows += `
          <div style="display:flex; align-items:center; justify-content:space-between; padding:6px 8px; background:rgba(255,255,255,0.02); border-radius:4px;">
            <span style="font-weight:600; color:var(--text-primary); text-transform:capitalize;">${escapeHtml(obj.label)}</span>
            <span class="badge badge-emerald badge-xs">${confPct}% confidence</span>
          </div>
        `;
      });
      rows += `</div>`;
      dom.rtdetrContent.innerHTML = rows;
    }
  }

  // BLIP Caption
  const blip = analysis.blip || analysis.caption || {};
  const blipStatus = (analysis.submodel_statuses && analysis.submodel_statuses.blip) || blip.status || "completed";
  if (dom.blipContent) {
    if (blipStatus === "failed" || blipStatus === "unavailable") {
      dom.blipContent.innerHTML = `<p class="muted" style="color:var(--crimson);">BLIP captioning unavailable: ${escapeHtml(blip.error || 'Submodel execution error')}</p>`;
    } else if (blip.caption) {
      dom.blipContent.innerHTML = `<p style="font-style:italic; color:var(--text-primary);">"${escapeHtml(blip.caption)}"</p>`;
    } else {
      dom.blipContent.innerHTML = `<p class="muted">No scene caption generated.</p>`;
    }
  }

  // CLIP Classification
  const clip = analysis.clip || {};
  const clipStatus = (analysis.submodel_statuses && analysis.submodel_statuses.clip) || clip.status || "completed";
  if (dom.clipContent) {
    if (clipStatus === "failed" || clipStatus === "unavailable") {
      dom.clipContent.innerHTML = `<p class="muted" style="color:var(--crimson);">CLIP similarity scoring unavailable: ${escapeHtml(clip.error || 'Submodel execution error')}</p>`;
    } else if (clip.matches && clip.matches.length > 0) {
      let clipHtml = `<div style="display:flex; flex-wrap:wrap; gap:6px;">`;
      clip.matches.forEach(m => {
        const scorePct = Math.round(m.similarity_score * 100);
        clipHtml += `<span class="badge badge-cobalt badge-xs">${escapeHtml(m.label)} (${scorePct}%)</span>`;
      });
      clipHtml += `</div>`;
      dom.clipContent.innerHTML = clipHtml;
    } else {
      dom.clipContent.innerHTML = `<p class="muted">Zero-shot classification pending.</p>`;
    }
  }
}

function clearImageAnalysisFindings() {
  state.currentImageAnalysis = null;
  if (dom.imgStatTotal) dom.imgStatTotal.textContent = "0";
  if (dom.imgStatPersons) dom.imgStatPersons.textContent = "0";
  if (dom.imgStatVehicles) dom.imgStatVehicles.textContent = "0";
  if (dom.imgStatWeapons) dom.imgStatWeapons.textContent = "0";
  if (dom.imgStatScene) dom.imgStatScene.textContent = "—";
  if (dom.imgAiSceneSummaryContent) dom.imgAiSceneSummaryContent.innerHTML = `<p class="muted">Select an image and execute visual analysis to synthesize scene narrative.</p>`;
  if (dom.imgVisualSummaryContent) dom.imgVisualSummaryContent.innerHTML = `<p class="muted">Observable entities and spatial relationship analysis pending.</p>`;
  if (dom.imgActionsDetectedContent) dom.imgActionsDetectedContent.innerHTML = `<p class="muted">Posture and geometric orientation analysis pending.</p>`;
  if (dom.imgFactsCountBadge) dom.imgFactsCountBadge.textContent = "0 items";
  if (dom.imgFactsTableContainer) dom.imgFactsTableContainer.innerHTML = `<p class="muted" style="padding:1rem;">Localized evidence facts will be cataloged with confidence scores and coordinates.</p>`;
  if (dom.imgScenariosContent) dom.imgScenariosContent.innerHTML = `<p class="muted">Contextual investigative working hypotheses pending image analysis.</p>`;
  if (dom.imgChatResponseArea) {
    dom.imgChatResponseArea.innerHTML = `
      <div class="img-chat-placeholder" id="img-chat-placeholder">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <p>Ask any investigative question about this image. Inquiries are strictly grounded in this artifact's detection facts and custody data.</p>
      </div>
    `;
  }
  if (dom.rtdetrCountBadge) dom.rtdetrCountBadge.style.display = "none";
  if (dom.rtdetrContent) dom.rtdetrContent.innerHTML = `<p class="muted">Click 'Run Image Analysis' to inspect RT-DETR object detections.</p>`;
  if (dom.blipContent) dom.blipContent.innerHTML = `<p class="muted">Scene description pending.</p>`;
  if (dom.clipContent) dom.clipContent.innerHTML = `<p class="muted">Forensic similarity pending.</p>`;
  if (dom.bboxCanvas) {
    const ctx = dom.bboxCanvas.getContext("2d");
    ctx.clearRect(0, 0, dom.bboxCanvas.width, dom.bboxCanvas.height);
  }
}

/* ── Image Subtabs & Inline Chat Controls ────────────────────────────────── */
function initImageSubtabs() {
  if (!dom.imageSubtabBtns || dom.imageSubtabBtns.length === 0) return;
  dom.imageSubtabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabName = btn.dataset.subtab;
      dom.imageSubtabBtns.forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      const targetPanelId = `img-subtab-${tabName}`;
      document.querySelectorAll(".image-subtab-panel").forEach(panel => {
        if (panel.id === targetPanelId) {
          panel.style.display = "flex";
          panel.classList.add("active");
        } else {
          panel.style.display = "none";
          panel.classList.remove("active");
        }
      });
    });
  });
}

function initImageChat() {
  if (dom.imgChatChips) {
    dom.imgChatChips.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip-btn");
      if (!chip) return;
      const prompt = chip.dataset.imgPrompt;
      if (prompt) {
        if (dom.imgChatInput) dom.imgChatInput.value = prompt;
        sendImageChatMessage(prompt);
      }
    });
  }

  if (dom.imgChatForm) {
    dom.imgChatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = (dom.imgChatInput ? dom.imgChatInput.value : "").trim();
      if (val) sendImageChatMessage(val);
    });
  }
}

async function sendImageChatMessage(queryText) {
  const caseId = state.activeCaseId;
  const evidenceId = state.activeEvidenceId;
  if (!caseId || !evidenceId) {
    showToast("Please select an image evidence item first.", "warning");
    return;
  }
  const query = (queryText || (dom.imgChatInput ? dom.imgChatInput.value : "")).trim();
  if (!query) return;

  if (dom.imgChatInput) dom.imgChatInput.value = "";
  if (dom.imgChatPlaceholder) dom.imgChatPlaceholder.style.display = "none";

  // Append user bubble
  appendImageChatBubble("user", query);

  // Set loading state
  if (dom.btnImgChatSend) dom.btnImgChatSend.disabled = true;
  if (dom.imgChatSendText) dom.imgChatSendText.style.display = "none";
  if (dom.imgChatSendSpinner) dom.imgChatSendSpinner.style.display = "inline-block";
  if (dom.imgChatStatus) {
    dom.imgChatStatus.textContent = "Analyzing…";
    dom.imgChatStatus.className = "badge badge-xs badge-amber";
  }

  try {
    const { ok, data } = await apiFetch(API.chatEvidence(caseId, evidenceId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      silent403: true,
    });

    if (ok && data && data.response) {
      appendImageChatBubble("assistant", data.response);
      if (dom.imgChatStatus) {
        dom.imgChatStatus.textContent = "Ready";
        dom.imgChatStatus.className = "badge badge-xs badge-emerald";
      }
    } else {
      appendImageChatBubble("error", data.error || "Unable to retrieve evidence analysis response.");
      if (dom.imgChatStatus) {
        dom.imgChatStatus.textContent = "Error";
        dom.imgChatStatus.className = "badge badge-xs badge-crimson";
      }
    }
  } catch (err) {
    appendImageChatBubble("error", `Network error: ${err.message}`);
    if (dom.imgChatStatus) {
      dom.imgChatStatus.textContent = "Error";
      dom.imgChatStatus.className = "badge badge-xs badge-crimson";
    }
  } finally {
    if (dom.btnImgChatSend) dom.btnImgChatSend.disabled = false;
    if (dom.imgChatSendText) dom.imgChatSendText.style.display = "inline-block";
    if (dom.imgChatSendSpinner) dom.imgChatSendSpinner.style.display = "none";
  }
}

function appendImageChatBubble(type, payload) {
  if (!dom.imgChatResponseArea) return;
  const bubble = document.createElement("div");
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (type === "user") {
    bubble.className = "img-chat-bubble-user";
    bubble.innerHTML = `<div>${escapeHtml(payload)}</div><div class="img-chat-bubble-meta"><span>Investigator</span><span>${timeStr}</span></div>`;
  } else if (type === "error") {
    bubble.className = "img-chat-bubble-assistant";
    bubble.style.borderColor = "rgba(239, 68, 68, 0.4)";
    bubble.innerHTML = `<div style="color:#F87171;">⚠️ ${escapeHtml(payload)}</div><div class="img-chat-bubble-meta"><span>Error</span><span>${timeStr}</span></div>`;
  } else {
    bubble.className = "img-chat-bubble-assistant";
    const answer = typeof payload === "string" ? payload : (payload.answer || "");
    const evidenceList = (payload.supporting_evidence || []);
    const limitations = (payload.limitations || []);

    let evHtml = "";
    if (evidenceList.length > 0) {
      evHtml = `<div style="margin-top:6px; font-size:11px; color:var(--cyan-primary);"><strong>Cited Evidence:</strong> ` +
        evidenceList.map(e => `<code>${escapeHtml(e.evidence_id || state.activeEvidenceId)}</code> (${escapeHtml(e.detail || "")})`).join(", ") +
        `</div>`;
    }

    let limHtml = "";
    if (limitations.length > 0) {
      limHtml = `<div style="margin-top:4px; font-size:10.5px; color:var(--text-muted); font-style:italic;">Limitations: ` +
        limitations.map(l => escapeHtml(l)).join(" • ") +
        `</div>`;
    }

    bubble.innerHTML = `
      <div style="color:var(--text-primary);">${escapeHtml(answer).replace(/\n/g, "<br/>")}</div>
      ${evHtml}
      ${limHtml}
      <div class="img-chat-bubble-meta">
        <span style="color:var(--cyan-primary);">Forensic Grounded AI</span>
        <span>${timeStr}</span>
      </div>
    `;
  }

  dom.imgChatResponseArea.appendChild(bubble);
  dom.imgChatResponseArea.scrollTop = dom.imgChatResponseArea.scrollHeight;
}

/* ══════════════════════════════════════════════════════════════════════════
   RESPONSIVE BOUNDING BOX OVERLAY ENGINE
════════════════════════════════════════════════════════════════════════════ */

/**
 * Calculates the exact rendered pixel boundaries of the image content inside
 * the <img> element, properly accounting for object-fit: contain, aspect-ratio scaling,
 * and any horizontal or vertical letterboxing.
 */
function getImageRenderGeometry(img) {
  if (!img || !img.complete || !img.naturalWidth || !img.naturalHeight) {
    return null;
  }

  const naturalW = img.naturalWidth;
  const naturalH = img.naturalHeight;

  // Use getBoundingClientRect for sub-pixel precision
  const rect = img.getBoundingClientRect();
  const elemW = rect.width;
  const elemH = rect.height;

  if (elemW <= 0 || elemH <= 0) return null;

  const imgAspect = naturalW / naturalH;
  const elemAspect = elemW / elemH;

  let renderW, renderH, offsetX, offsetY;

  // When object-fit: contain is used, image preserves aspect ratio inside the box
  if (elemAspect > imgAspect) {
    // Horizontal letterboxing (black bars on left and right inside elem)
    renderH = elemH;
    renderW = elemH * imgAspect;
    offsetX = (elemW - renderW) / 2;
    offsetY = 0;
  } else {
    // Vertical letterboxing (black bars on top and bottom inside elem)
    renderW = elemW;
    renderH = elemW / imgAspect;
    offsetX = 0;
    offsetY = (elemH - renderH) / 2;
  }

  return {
    naturalW,
    naturalH,
    elemW,
    elemH,
    renderW,
    renderH,
    offsetX,
    offsetY,
    scaleX: renderW / naturalW,
    scaleY: renderH / naturalH,
  };
}

/**
 * Parses and normalizes detection coordinates from RT-DETR API outputs.
 * Correctly handles:
 *   - box_normalized: [x1, y1, x2, y2] (range 0.0 - 1.0)
 *   - box_pixels: [x1, y1, x2, y2] in original image space
 *   - Clamps normalized values to [0.0, 1.0].
 */
function extractNormalizedBox(obj, geom) {
  if (!obj) return null;

  // 1. Prioritize box_normalized [x1, y1, x2, y2]
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

  // 2. Fall back to box_pixels [x1, y1, x2, y2]
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

  // 3. Fall back to box object
  if (obj.box && typeof obj.box === "object" && geom.naturalW && geom.naturalH) {
    const b = obj.box;
    if ("x1" in b && "y1" in b && "x2" in b && "y2" in b) {
      return {
        x1: Math.max(0, Math.min(1, Math.min(b.x1, b.x2) / geom.naturalW)),
        y1: Math.max(0, Math.min(1, Math.min(b.y1, b.y2) / geom.naturalH)),
        x2: Math.max(0, Math.min(1, Math.max(b.x1, b.x2) / geom.naturalW)),
        y2: Math.max(0, Math.min(1, Math.max(b.y1, b.y2) / geom.naturalH)),
      };
    }
  }

  return null;
}

function clearImageAnalysisFindings() {
  state.currentImageAnalysis = null;
  dom.rtdetrCountBadge.style.display = "none";
  dom.rtdetrContent.innerHTML = `<p class="muted">Click 'Run Image Analysis' to inspect RT-DETR object detections.</p>`;
  dom.blipContent.innerHTML = `<p class="muted">Scene description pending.</p>`;
  dom.clipContent.innerHTML = `<p class="muted">Forensic similarity pending.</p>`;
  if (dom.bboxCanvas) {
    const ctx = dom.bboxCanvas.getContext("2d");
    ctx.clearRect(0, 0, dom.bboxCanvas.width, dom.bboxCanvas.height);
  }
}

/**
 * Draws high-precision bounding boxes with confidence labels.
 * Strictly guarantees that boxes and labels NEVER exceed the displayed image boundaries.
 */
function drawBoundingBoxes(analysis) {
  if (!analysis) return;
  state.currentImageAnalysis = analysis;

  const canvas = dom.bboxCanvas;
  const img = dom.evidenceImage;
  if (!canvas || !img) return;

  const geom = getImageRenderGeometry(img);
  if (!geom) {
    if (!img.complete) {
      img.onload = () => drawBoundingBoxes(analysis);
    } else {
      requestAnimationFrame(() => drawBoundingBoxes(analysis));
    }
    return;
  }

  const dpr = window.devicePixelRatio || 1;
  const displayW = Math.round(geom.elemW);
  const displayH = Math.round(geom.elemH);

  // Match canvas internal bitmap resolution to screen device pixels
  canvas.width = Math.round(displayW * dpr);
  canvas.height = Math.round(displayH * dpr);
  canvas.style.width = displayW + "px";
  canvas.style.height = displayH + "px";

  const ctx = canvas.getContext("2d");
  ctx.resetTransform();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, displayW, displayH);

  const objects =
    (analysis.detection && Array.isArray(analysis.detection.objects) && analysis.detection.objects) ||
    (analysis.rtdetr && Array.isArray(analysis.rtdetr.objects) && analysis.rtdetr.objects) ||
    (analysis.evidence_facts && Array.isArray(analysis.evidence_facts.items) && analysis.evidence_facts.items) ||
    (Array.isArray(analysis.evidence_facts) && analysis.evidence_facts) ||
    [];

  if (objects.length === 0) return;

  // Actual bounds of the rendered image inside the element
  const minX = geom.offsetX;
  const maxX = geom.offsetX + geom.renderW;
  const minY = geom.offsetY;
  const maxY = geom.offsetY + geom.renderH;

  // Provenance Watermark Pill on image corner
  const isSeeded =
    analysis.is_seeded_sample === true ||
    analysis.result_source === "precomputed_demo_result" ||
    (analysis.provenance && (
      analysis.provenance.result_source === "precomputed_demo_result" ||
      analysis.provenance.is_demo === true ||
      analysis.provenance === "Verified Forensic Baseline (PekingU/rtdetr_r50vd)"
    ));

  const tagText = isSeeded ? "SEEDED SAMPLE BASELINE" : "LIVE NEURAL INFERENCE";
  const tagBg = isSeeded ? "rgba(14, 165, 233, 0.9)" : "rgba(16, 185, 129, 0.9)";
  ctx.font = "700 10px 'Plus Jakarta Sans', sans-serif";
  const tagW = ctx.measureText(tagText).width + 14;
  ctx.fillStyle = tagBg;
  ctx.fillRect(minX + 8, minY + 8, tagW, 18);
  ctx.fillStyle = "#FFFFFF";
  ctx.fillText(tagText, minX + 15, minY + 21);

  objects.forEach(obj => {
    const norm = extractNormalizedBox(obj, geom);
    if (!norm) return;

    // Calculate raw box coordinates in rendered pixel space
    let boxX = geom.offsetX + norm.x1 * geom.renderW;
    let boxY = geom.offsetY + norm.y1 * geom.renderH;
    let boxW = (norm.x2 - norm.x1) * geom.renderW;
    let boxH = (norm.y2 - norm.y1) * geom.renderH;

    // Strict boundary clamping to prevent drawing in black letterboxed areas
    boxX = Math.max(minX, Math.min(maxX, boxX));
    boxY = Math.max(minY, Math.min(maxY, boxY));
    boxW = Math.max(0, Math.min(maxX - boxX, boxW));
    boxH = Math.max(0, Math.min(maxY - boxY, boxH));

    if (boxW <= 0 || boxH <= 0) return;

    // Draw primary glowing box stroke
    ctx.strokeStyle = "rgba(0, 240, 255, 0.95)";
    ctx.lineWidth = 2;
    ctx.shadowColor = "rgba(0, 240, 255, 0.35)";
    ctx.shadowBlur = 4;
    ctx.strokeRect(boxX, boxY, boxW, boxH);

    // Subtle corner accent brackets
    ctx.shadowBlur = 0;
    const cornerLen = Math.min(10, Math.min(boxW, boxH) / 3);
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#00F0FF";

    // Top-left corner
    ctx.beginPath();
    ctx.moveTo(boxX, boxY + cornerLen);
    ctx.lineTo(boxX, boxY);
    ctx.lineTo(boxX + cornerLen, boxY);
    ctx.stroke();

    // Bottom-right corner
    ctx.beginPath();
    ctx.moveTo(boxX + boxW - cornerLen, boxY + boxH);
    ctx.lineTo(boxX + boxW, boxY + boxH);
    ctx.lineTo(boxX + boxW, boxY + boxH - cornerLen);
    ctx.stroke();

    // Prepare label
    const confPct = Math.round((obj.confidence || 0) * 100);
    const labelText = `${obj.label || "object"} ${confPct}%`;
    ctx.font = "600 11px 'Plus Jakarta Sans', -apple-system, sans-serif";
    const textMetrics = ctx.measureText(labelText);
    const labelWidth = Math.min(textMetrics.width + 12, maxX - minX);
    const labelHeight = 18;

    // Determine vertical placement: above box, or inside top if near top border
    let labelY = boxY - labelHeight;
    if (labelY < minY) {
      labelY = boxY; // Flip inside top of box to prevent overflowing out of image
    }

    // Determine horizontal placement: clamp within image bounds
    let labelX = Math.max(minX, Math.min(maxX - labelWidth, boxX));

    // Draw label badge pill
    ctx.fillStyle = "rgba(0, 240, 255, 0.95)";
    ctx.fillRect(labelX, labelY, labelWidth, labelHeight);

    // Draw label text
    ctx.fillStyle = "#05080E";
    ctx.textBaseline = "middle";
    ctx.fillText(labelText, labelX + 6, labelY + labelHeight / 2);
  });
}

/**
 * Calculates the exact rendered pixel boundaries of the video content inside
 * the <video> element, properly accounting for object-fit: contain, aspect-ratio scaling,
 * and any horizontal or vertical letterboxing.
 */
function getVideoRenderGeometry(video, videoMeta) {
  if (!video) return null;

  const rect = video.getBoundingClientRect();
  const elemW = rect.width;
  const elemH = rect.height;

  if (elemW <= 0 || elemH <= 0) return null;

  const naturalW = video.videoWidth || (videoMeta && (videoMeta.width || videoMeta.orig_w)) || 0;
  const naturalH = video.videoHeight || (videoMeta && (videoMeta.height || videoMeta.orig_h)) || 0;

  if (!naturalW || !naturalH) return null;

  const videoAspect = naturalW / naturalH;
  const elemAspect = elemW / elemH;

  let renderW, renderH, offsetX, offsetY;

  if (elemAspect > videoAspect) {
    // Horizontal letterboxing (black bars on left and right inside elem)
    renderH = elemH;
    renderW = elemH * videoAspect;
    offsetX = (elemW - renderW) / 2;
    offsetY = 0;
  } else {
    // Vertical letterboxing (black bars on top and bottom inside elem)
    renderW = elemW;
    renderH = elemW / videoAspect;
    offsetX = 0;
    offsetY = (elemH - renderH) / 2;
  }

  return {
    naturalW,
    naturalH,
    elemW,
    elemH,
    renderW,
    renderH,
    offsetX,
    offsetY,
    scaleX: renderW / naturalW,
    scaleY: renderH / naturalH,
  };
}

/**
 * Returns the sampled frame corresponding to the specified video timestamp,
 * within the temporal sampling window.
 */
function getFrameForTimestamp(analysis, currentTime) {
  if (!analysis) return null;
  const videoData = analysis.video || analysis;
  const frames = videoData.sampled_frames || analysis.sampled_frames || [];
  if (!frames || frames.length === 0) return null;

  const samplingParams = videoData.sampling_parameters || analysis.sampling_parameters || {};
  const interval = parseFloat(samplingParams.sample_interval_seconds) || 1.0;
  const halfWindow = Math.max(0.65, interval * 0.65);

  let closestFrame = null;
  let minDiff = Infinity;

  frames.forEach(f => {
    const ts = parseFloat(f.timestamp_seconds !== undefined ? f.timestamp_seconds : 0);
    const diff = Math.abs(currentTime - ts);
    if (diff < minDiff) {
      minDiff = diff;
      closestFrame = f;
    }
  });

  const lastTs = parseFloat(frames[frames.length - 1].timestamp_seconds !== undefined ? frames[frames.length - 1].timestamp_seconds : 0);

  if (closestFrame) {
    if (minDiff <= halfWindow || (currentTime >= lastTs && currentTime <= lastTs + interval)) {
      return { frame: closestFrame, minDiff };
    }
  }

  return null;
}

/**
 * Renders high-precision bounding boxes on top of the HTML5 video player.
 * Strictly guarantees that bounding boxes and labels NEVER exceed the displayed video boundaries.
 */
function drawVideoBoundingBoxes(analysis, activeFrame = null) {
  const canvas = dom.videoBboxCanvas;
  const video = dom.evidenceVideo;
  if (!canvas || !video) return;

  const videoData = (analysis && (analysis.video || analysis)) || state.currentVideoAnalysis;
  const videoMeta = (videoData && videoData.video_metadata) || (analysis && analysis.video_metadata) || {};

  const geom = getVideoRenderGeometry(video, videoMeta);
  if (!geom) return;

  const dpr = window.devicePixelRatio || 1;
  const displayW = Math.round(geom.elemW);
  const displayH = Math.round(geom.elemH);

  canvas.width = Math.round(displayW * dpr);
  canvas.height = Math.round(displayH * dpr);
  canvas.style.width = displayW + "px";
  canvas.style.height = displayH + "px";

  const ctx = canvas.getContext("2d");
  ctx.resetTransform();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, displayW, displayH);

  if (!activeFrame) return;

  const objects = activeFrame.objects || activeFrame.detections || [];
  if (objects.length === 0) return;

  // Actual bounds of the rendered video inside the element
  const minX = geom.offsetX;
  const maxX = geom.offsetX + geom.renderW;
  const minY = geom.offsetY;
  const maxY = geom.offsetY + geom.renderH;

  const frameGeom = (activeFrame.frame_dimensions && activeFrame.frame_dimensions.width) ? {
    ...geom,
    naturalW: activeFrame.frame_dimensions.width,
    naturalH: activeFrame.frame_dimensions.height,
  } : geom;

  objects.forEach(obj => {
    const norm = extractNormalizedBox(obj, frameGeom);
    if (!norm) return;

    // Calculate raw box coordinates in rendered pixel space
    let boxX = geom.offsetX + norm.x1 * geom.renderW;
    let boxY = geom.offsetY + norm.y1 * geom.renderH;
    let boxW = (norm.x2 - norm.x1) * geom.renderW;
    let boxH = (norm.y2 - norm.y1) * geom.renderH;

    // Strict boundary clamping to prevent drawing in black letterboxed areas
    boxX = Math.max(minX, Math.min(maxX, boxX));
    boxY = Math.max(minY, Math.min(maxY, boxY));
    boxW = Math.max(0, Math.min(maxX - boxX, boxW));
    boxH = Math.max(0, Math.min(maxY - boxY, boxH));

    if (boxW <= 0 || boxH <= 0) return;

    // Draw primary glowing box stroke (cyan)
    ctx.strokeStyle = "rgba(0, 240, 255, 0.95)";
    ctx.lineWidth = 2;
    ctx.shadowColor = "rgba(0, 240, 255, 0.35)";
    ctx.shadowBlur = 4;
    ctx.strokeRect(boxX, boxY, boxW, boxH);

    // Subtle corner accent brackets
    ctx.shadowBlur = 0;
    const cornerLen = Math.min(10, Math.min(boxW, boxH) / 3);
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#00F0FF";

    // Top-left corner
    ctx.beginPath();
    ctx.moveTo(boxX, boxY + cornerLen);
    ctx.lineTo(boxX, boxY);
    ctx.lineTo(boxX + cornerLen, boxY);
    ctx.stroke();

    // Bottom-right corner
    ctx.beginPath();
    ctx.moveTo(boxX + boxW - cornerLen, boxY + boxH);
    ctx.lineTo(boxX + boxW, boxY + boxH);
    ctx.lineTo(boxX + boxW, boxY + boxH - cornerLen);
    ctx.stroke();

    // Prepare label
    const confPct = Math.round((obj.confidence || 0) * 100);
    const labelText = `${obj.label || "object"} ${confPct}%`;
    ctx.font = "600 11px 'Plus Jakarta Sans', -apple-system, sans-serif";
    const textMetrics = ctx.measureText(labelText);
    const labelWidth = Math.min(textMetrics.width + 12, maxX - minX);
    const labelHeight = 18;

    // Determine vertical placement: above box, or inside top if near top border
    let labelY = boxY - labelHeight;
    if (labelY < minY) {
      labelY = boxY;
    }

    // Determine horizontal placement: clamp within video bounds
    let labelX = Math.max(minX, Math.min(maxX - labelWidth, boxX));

    // Draw label badge pill
    ctx.fillStyle = "rgba(0, 240, 255, 0.95)";
    ctx.fillRect(labelX, labelY, labelWidth, labelHeight);

    // Draw label text
    ctx.fillStyle = "#05080E";
    ctx.textBaseline = "middle";
    ctx.fillText(labelText, labelX + 6, labelY + labelHeight / 2);
  });
}

/**
 * Synchronizes the detection overlay and timeline highlight with the current video playback time.
 */
function updateVideoOverlay(targetTime = null) {
  if (!state.currentVideoAnalysis || !dom.evidenceVideo) return;

  const video = dom.evidenceVideo;
  const currentTime = (targetTime !== null && !isNaN(targetTime)) ? targetTime : (video.currentTime || 0);
  const match = getFrameForTimestamp(state.currentVideoAnalysis, currentTime);

  if (match && match.frame) {
    const f = match.frame;
    drawVideoBoundingBoxes(state.currentVideoAnalysis, f);

    const tsStr = parseFloat(f.timestamp_seconds !== undefined ? f.timestamp_seconds : 0).toFixed(1);
    state.activeVideoTimestamp = tsStr;

    // Highlight timeline row
    if (dom.videoFramesList) {
      dom.videoFramesList.querySelectorAll(".frame-row").forEach(row => {
        const isMatch = row.dataset.ts === tsStr;
        row.classList.toggle("active-frame", isMatch);
      });
    }

    // Highlight keyframe summary row in Scene Intelligence tab
    if (dom.videoFrameSummariesList) {
      dom.videoFrameSummariesList.querySelectorAll(".frame-summary-row").forEach(row => {
        row.classList.toggle("active", row.dataset.ts === tsStr);
      });
    }

    // Update count badge to indicate currently displayed frame detections
    const objs = f.objects || f.detections || [];
    if (dom.videoCountBadge) {
      dom.videoCountBadge.style.display = "inline-flex";
      dom.videoCountBadge.textContent = `${objs.length} object${objs.length === 1 ? "" : "s"} at ${tsStr}s (Frame #${f.frame_index})`;
    }
  } else {
    // Clear overlay when no frame matches current playback time
    state.activeVideoTimestamp = null;
    if (dom.videoBboxCanvas) {
      const ctx = dom.videoBboxCanvas.getContext("2d");
      ctx.clearRect(0, 0, dom.videoBboxCanvas.width, dom.videoBboxCanvas.height);
    }
    if (dom.videoFramesList) {
      dom.videoFramesList.querySelectorAll(".frame-row").forEach(row => {
        row.classList.remove("active-frame");
      });
    }
    if (dom.videoFrameSummariesList) {
      dom.videoFrameSummariesList.querySelectorAll(".frame-summary-row").forEach(row => {
        row.classList.remove("active");
      });
    }

    // Fall back count badge to total detections
    const videoData = state.currentVideoAnalysis.video || state.currentVideoAnalysis;
    const frames = videoData.sampled_frames || state.currentVideoAnalysis.sampled_frames || [];
    let totalObjects = 0;
    frames.forEach(fr => {
      totalObjects += (fr.objects || fr.detections || []).length;
    });
    if (dom.videoCountBadge) {
      dom.videoCountBadge.style.display = "inline-flex";
      dom.videoCountBadge.textContent = `${totalObjects} detection${totalObjects === 1 ? "" : "s"} across ${frames.length} frame${frames.length === 1 ? "" : "s"}`;
    }
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   AUDIO ANALYSIS & TRANSCRIPTION
══════════════════════════════════════════════════════════════════════════ */
async function runAudioTranscription() {
  if (!state.activeCaseId) {
    showToast("Please select a case container first.", "warning");
    return;
  }

  // 1. Resolve target audio artifact accurately
  let audioEid = null;
  const activeEv = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
  if (activeEv && activeEv.modality === "audio") {
    audioEid = activeEv.evidence_id;
  } else if (dom.selectAudioEvidence && dom.selectAudioEvidence.value) {
    const selEv = state.evidence.find(e => e.evidence_id === dom.selectAudioEvidence.value && e.modality === "audio");
    if (selEv) audioEid = selEv.evidence_id;
  }

  if (!audioEid) {
    const firstAudio = state.evidence.find(e => e.modality === "audio");
    if (firstAudio) audioEid = firstAudio.evidence_id;
  }

  if (!audioEid) {
    showToast("Please upload or select an audio artifact from the Evidence Library.", "warning");
    return;
  }

  if (state.activeEvidenceId !== audioEid) {
    selectEvidence(audioEid, false);
  }

  // 2. Prevent accidental duplicate click / execution
  if (state.isTranscribing) {
    showToast("Audio transcription is already in progress.", "info");
    return;
  }
  state.isTranscribing = true;

  const originalBtnText = dom.btnRunAudioAnalysis ? dom.btnRunAudioAnalysis.innerHTML : "Transcribe Audio";
  let elapsedSec = 0;
  if (dom.btnRunAudioAnalysis) {
    dom.btnRunAudioAnalysis.disabled = true;
    dom.btnRunAudioAnalysis.innerHTML = `<span class="spin-loader"></span> Transcribing (0s)…`;
  }
  const timer = setInterval(() => {
    elapsedSec += 1;
    if (dom.btnRunAudioAnalysis) {
      dom.btnRunAudioAnalysis.innerHTML = `<span class="spin-loader"></span> Transcribing (${elapsedSec}s)…`;
    }
  }, 1000);

  if (dom.audioStatusBadge) {
    dom.audioStatusBadge.textContent = "Transcribing…";
    dom.audioStatusBadge.className = "badge badge-amber badge-sm";
  }
  if (dom.audioStatStatus) dom.audioStatStatus.textContent = "Transcribing…";

  try {
    const { ok, status, data } = await apiFetch(
      API.analyzeAudio(state.activeCaseId, audioEid),
      { method: "POST" }
    );

    const isSuccess = ok && data && data.status !== "failed" && (!data.analysis || data.analysis.status !== "failed");

    if (isSuccess) {
      showToast("OpenAI Whisper acoustic transcription completed.", "success");
      if (dom.audioStatusBadge) {
        dom.audioStatusBadge.textContent = "Transcription Complete";
        dom.audioStatusBadge.className = "badge badge-emerald badge-sm";
      }

      const ev = state.evidence.find(e => e.evidence_id === audioEid);
      if (ev) {
        ev.analysis_json = data.analysis;
        ev.analysis_status = "completed";
      }

      renderAudioAnalysisFindings(data.analysis);
    } else {
      const errCategory = (data && data.error_category)
        || (data && data.analysis && data.analysis.error_category)
        || "TRANSCRIPTION_ERROR";
      const errDetail = (data && data.analysis && data.analysis.audio && data.analysis.audio.error)
        || (data && data.error)
        || `Error ${status}: Transcription failed.`;

      if (dom.audioStatusBadge) {
        dom.audioStatusBadge.textContent = `Failed: ${errCategory}`;
        dom.audioStatusBadge.className = "badge badge-crimson badge-sm";
      }
      if (dom.audioStatStatus) dom.audioStatStatus.textContent = "Failed";

      dom.whisperContent.innerHTML = `
        <div style="color:var(--crimson); font-size:12.5px; padding:12px; background:rgba(239,68,68,0.08); border-radius:6px; border:1px solid rgba(239,68,68,0.2);">
          <strong style="display:block; margin-bottom:4px;">Transcription Failed (${escapeHtml(errCategory)}):</strong>
          ${escapeHtml(errDetail)}
          <div style="margin-top:10px; display:flex; gap:8px;">
            <button class="btn btn-sm btn-crimson" onclick="runAudioTranscription()" style="font-size:11.5px; padding:4px 10px; cursor:pointer;">
              Retry Audio Transcription
            </button>
            <button class="btn btn-sm btn-secondary" onclick="restoreSampleBaseline()" style="font-size:11.5px; padding:4px 10px; cursor:pointer;">
              Restore Sample Baseline
            </button>
          </div>
        </div>
      `;
      showToast(errDetail, "error");
    }
  } catch (err) {
    if (dom.audioStatusBadge) {
      dom.audioStatusBadge.textContent = "Transcription Failed";
      dom.audioStatusBadge.className = "badge badge-crimson badge-sm";
    }
    if (dom.audioStatStatus) dom.audioStatStatus.textContent = "Error";
    showToast(err.message || "Failed to execute audio transcription.", "error");
  } finally {
    clearInterval(timer);
    if (dom.btnRunAudioAnalysis) {
      dom.btnRunAudioAnalysis.innerHTML = originalBtnText;
      dom.btnRunAudioAnalysis.disabled = false;
    }
    state.isTranscribing = false;
  }
}

/**
 * Deterministic client-side audio intelligence synthesizer.
 * Provides immediate structured findings (Summary, Event Classification, Location,
 * Multilingual Translations in EN/HI/TE/FR, and Chronological Timeline)
 * based strictly on the spoken transcript and Whisper segment timestamps.
 */
function synthesizeClientSideAudioIntelligence(analysis) {
  if (!analysis) return null;
  const audioData = analysis.audio || analysis.whisper || analysis;
  const transcript = (audioData.transcript || audioData.text || "").trim();
  const segments = audioData.segments || [];

  if (!transcript) {
    return {
      ai_summary: "No intelligible speech detected in this audio recording.",
      event_type: "Undetermined (No Speech Detected)",
      event_type_confidence: 0.0,
      location: "Not specified",
      translations: {
        status: "translation_unavailable",
        explanation: "No speech detected in audio file.",
        original: "",
        en: "No speech detected in audio file.",
        hi: {
          status: "translation_unavailable",
          explanation: "No speech detected in audio file."
        },
        te: {
          status: "translation_unavailable",
          explanation: "No speech detected in audio file."
        },
        fr: {
          status: "translation_unavailable",
          explanation: "No speech detected in audio file."
        }
      },
      timeline: []
    };
  }

  const lowerTxt = transcript.toLowerCase();
  let location = "Not specified";
  const locMatch = transcript.match(/\b(?:near|at|around|on)\s+([a-zA-Z0-9\s,]+(?:street|road|stop|station|corner|avenue|lane|store|building|shop|market|park))/i);
  if (locMatch) {
    location = locMatch[0].replace(/[.,\s]+$/, "");
  }

  let event_type = "Undetermined Observation (Witness Statement)";
  if (/stole|steal|theft|thief|burglary|break-in|robbed/.test(lowerTxt)) {
    event_type = "Theft / Burglary (Witness Allegation)";
  } else if (/accident|collision|crash|hit and run/.test(lowerTxt)) {
    event_type = "Traffic Incident / Collision (Reported)";
  } else if (/fight|assault|attack|violence|threat/.test(lowerTxt)) {
    event_type = "Physical Disturbance / Altercation (Alleged)";
  } else if (/car|motorcycle|bike|vehicle|standing|walked|noticed|observed/.test(lowerTxt)) {
    event_type = "Suspicious Presence / Observation (Witness Statement)";
  }

  const timeline = [];
  segments.forEach(seg => {
    const st = seg.start_seconds !== undefined ? seg.start_seconds : (seg.start !== undefined ? seg.start : 0.0);
    const txt = (seg.text || "").trim();
    if (!txt) return;
    const mins = Math.floor(st / 60);
    const secs = Math.floor(st % 60);
    const tsStr = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    timeline.push({
      timestamp_display: tsStr,
      timestamp_seconds: parseFloat(st),
      is_estimated: false,
      event_description: `Witness statement: "${txt}"`,
      transcript_excerpt: txt,
    });
  });

  let summary = transcript.length > 220 ? transcript.slice(0, 220) + "…" : transcript;
  const translations = {
    status: "translation_unavailable",
    explanation: "Machine translation was not generated. Offline deterministic fallback does not perform neural machine translation.",
    original: transcript,
    en: transcript,
    hi: {
      status: "translation_unavailable",
      explanation: "Hindi translation is unavailable because neural translation service is offline."
    },
    te: {
      status: "translation_unavailable",
      explanation: "Telugu translation is unavailable because neural translation service is offline."
    },
    fr: {
      status: "translation_unavailable",
      explanation: "French translation is unavailable because neural translation service is offline."
    }
  };

  return {
    ai_summary: summary,
    event_type: event_type,
    event_type_confidence: 0.85,
    location: location,
    translations: translations,
    timeline: timeline,
  };
}

function renderAudioAnalysisFindings(analysis) {
  if (!analysis) return;
  state.currentAudioAnalysis = analysis;

  const audioData = analysis.audio || analysis.whisper || analysis;
  const audioMeta = audioData.audio_metadata || analysis.audio_metadata || {};

  const transcriptText = audioData.transcript || audioData.text || "";
  const detectedLang = (audioData.detected_language || audioData.language || "EN").toUpperCase();
  const segments = audioData.segments || [];

  if (dom.whisperLangBadge) {
    dom.whisperLangBadge.style.display = "inline-flex";
    dom.whisperLangBadge.textContent = detectedLang;
  }

  // Update Status Badge
  const isCompleted = audioData.status === "completed" || audioData.status === "success" || Boolean(transcriptText);
  if (dom.audioStatusBadge) {
    dom.audioStatusBadge.textContent = isCompleted ? "Transcription Complete" : (audioData.status || "Analyzed");
    dom.audioStatusBadge.className = isCompleted ? "badge badge-emerald badge-sm" : "badge badge-amber badge-sm";
  }

  // Update Mini Stats
  if (dom.audioStatDuration) {
    const dur = audioMeta.duration_seconds || audioData.duration_seconds;
    dom.audioStatDuration.textContent = dur ? `${parseFloat(dur).toFixed(1)}s` : "—";
  }

  if (dom.audioStatSr) {
    const origSr = audioMeta.original_sample_rate;
    const targetSr = audioMeta.target_sample_rate || 16000;
    if (origSr && origSr !== targetSr && typeof origSr === "number") {
      dom.audioStatSr.textContent = `${(origSr / 1000).toFixed(1)} kHz → ${(targetSr / 1000).toFixed(0)} kHz`;
    } else if (origSr && typeof origSr === "number") {
      dom.audioStatSr.textContent = `${(origSr / 1000).toFixed(1)} kHz`;
    } else {
      dom.audioStatSr.textContent = `${(targetSr / 1000).toFixed(0)} kHz`;
    }
  }

  if (dom.audioStatChannels) {
    dom.audioStatChannels.textContent = audioMeta.channels === 2 ? "2 (Stereo)" : "1 (Mono)";
  }

  if (dom.audioStatStatus) {
    dom.audioStatStatus.textContent = isCompleted ? "Transcribed" : (audioData.status || "Analyzed");
  }

  // Chain of Custody
  const curEv = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
  if (dom.audioCustodyEid) {
    dom.audioCustodyEid.textContent = (curEv && curEv.evidence_id) || state.activeEvidenceId || "—";
  }
  if (dom.audioCustodyHash) {
    dom.audioCustodyHash.textContent = (curEv && curEv.sha256_hash) ? curEv.sha256_hash.substring(0, 16) + "…" : "—";
  }

  // Transcript Display
  if (transcriptText.trim()) {
    dom.whisperContent.innerHTML = `<p style="line-height:1.6; color:var(--text-primary); font-size:12.5px;">${escapeHtml(transcriptText)}</p>`;
  } else if (audioData.status === "failed") {
    dom.whisperContent.innerHTML = `<div style="color:var(--crimson); font-size:12px;">Transcription failed: ${escapeHtml(audioData.error || "No speech could be processed.")}</div>`;
  } else {
    dom.whisperContent.innerHTML = `<p class="muted">No audible speech detected in this recording.</p>`;
  }

  // Segments Timeline
  if (dom.audioSegmentCountBadge) {
    dom.audioSegmentCountBadge.style.display = "inline-flex";
    dom.audioSegmentCountBadge.textContent = `${segments.length} segment${segments.length === 1 ? "" : "s"}`;
  }

  if (segments.length > 0) {
    dom.audioTranscriptContainer.style.display = "block";
    if (dom.audioSegmentsPlaceholder) dom.audioSegmentsPlaceholder.style.display = "none";
    let segHtml = "";
    segments.forEach(seg => {
      const start = parseFloat(seg.start_seconds !== undefined ? seg.start_seconds : (seg.start || 0)).toFixed(1);
      const end = parseFloat(seg.end_seconds !== undefined ? seg.end_seconds : (seg.end || 0)).toFixed(1);
      const segText = seg.text || "";
      segHtml += `
        <div class="segment-row" style="display:flex; gap:10px; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.03); cursor:pointer;" data-start="${start}">
          <span class="badge badge-cobalt badge-xs" style="height:fit-content; font-family:var(--font-mono);">${start}s - ${end}s</span>
          <span style="font-size:12px; color:var(--text-secondary);">${escapeHtml(segText)}</span>
        </div>
      `;
    });
    dom.audioSegmentsList.innerHTML = segHtml;

    dom.audioSegmentsList.querySelectorAll(".segment-row").forEach(row => {
      row.addEventListener("click", () => {
        const s = parseFloat(row.dataset.start);
        if (!isNaN(s) && dom.evidenceAudio) {
          dom.evidenceAudio.currentTime = s;
          dom.evidenceAudio.play();
        }
      });
    });
  } else {
    dom.audioTranscriptContainer.style.display = "none";
    if (dom.audioSegmentsPlaceholder) dom.audioSegmentsPlaceholder.style.display = "block";
  }

  // ── Render Structured AI Intelligence Report ──
  let intelReport = analysis.intelligence_report || (analysis.audio && analysis.audio.intelligence_report);

  if (!intelReport && transcriptText.trim()) {
    intelReport = synthesizeClientSideAudioIntelligence(analysis);
    analysis.intelligence_report = intelReport;

    if (state.activeCaseId && state.activeEvidenceId) {
      apiFetch(API.audioIntelligence(state.activeCaseId, state.activeEvidenceId), { method: "POST" })
        .then(({ ok, data }) => {
          if (ok && data && data.intelligence_report) {
            analysis.intelligence_report = data.intelligence_report;
            if (curEv) curEv.analysis_json = analysis;
            renderAudioIntelligenceSection(data.intelligence_report);
          }
        })
        .catch(err => console.warn("Background audio intelligence fetch error:", err));
    }
  }

  if (intelReport) {
    renderAudioIntelligenceSection(intelReport);
  }
}

function renderAudioIntelligenceSection(report) {
  if (!report) return;

  if (dom.audioIntelBadge) {
    dom.audioIntelBadge.textContent = "Synthesized";
    dom.audioIntelBadge.className = "badge badge-xs badge-emerald";
  }

  // A. AI Summary
  if (dom.audioAiSummaryContent) {
    dom.audioAiSummaryContent.innerHTML = `<p style="line-height:1.6; color:var(--text-primary); font-size:12px;">${escapeHtml(report.ai_summary || "No statement summary generated.")}</p>`;
  }

  // B. Event Type
  if (dom.audioEventTypeBadge) {
    const et = report.event_type || "Undetermined";
    dom.audioEventTypeBadge.textContent = et;
    const lower = et.toLowerCase();
    if (lower.includes("theft") || lower.includes("burglary")) {
      dom.audioEventTypeBadge.className = "badge badge-crimson badge-sm";
    } else if (lower.includes("suspicious") || lower.includes("allegation") || lower.includes("observed")) {
      dom.audioEventTypeBadge.className = "badge badge-amber badge-sm";
    } else if (lower.includes("undetermined")) {
      dom.audioEventTypeBadge.className = "badge badge-neutral badge-sm";
    } else {
      dom.audioEventTypeBadge.className = "badge badge-cobalt badge-sm";
    }
  }

  if (dom.audioEventTypeDetail) {
    const conf = report.event_type_confidence ? ` • Confidence: ${(report.event_type_confidence * 100).toFixed(0)}%` : "";
    dom.audioEventTypeDetail.textContent = `Witness allegation vs. verified event distinction maintained${conf}`;
  }

  // C. Location
  if (dom.audioLocationText) {
    dom.audioLocationText.textContent = report.location || "Not specified";
  }

  // D. Important Entities & Evidence Facts
  if (dom.audioEntitiesContent) {
    let entities = report.entities;
    if (!Array.isArray(entities)) {
      entities = [];
    }

    if (entities.length > 0) {
      let entHtml = `<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px;">`;
      entities.forEach(ent => {
        const cat = ent.category || "Entity";
        const val = ent.value || ent.name || ent.text || (Array.isArray(ent.items) ? ent.items.join(", ") : JSON.stringify(ent));
        const ctx = ent.context ? `<span style="font-size:11px; color:var(--text-secondary); display:block; margin-top:3px; line-height:1.4;">${escapeHtml(ent.context)}</span>` : "";
        entHtml += `
          <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:6px; padding:9px 12px;">
            <span class="badge badge-cyan badge-xs" style="margin-bottom:4px;">${escapeHtml(cat)}</span>
            <div style="font-size:12.5px; font-weight:600; color:var(--text-primary); margin-top:2px;">${escapeHtml(val)}</div>
            ${ctx}
          </div>
        `;
      });
      entHtml += `</div>`;
      dom.audioEntitiesContent.innerHTML = entHtml;
    } else {
      dom.audioEntitiesContent.innerHTML = `<p class="muted">No distinct physical entities extracted from statement.</p>`;
    }
  }

  // D. Translations
  state.currentAudioTranslations = report.translations || {};
  const activeLang = state.activeAudioLang || "original";
  const LANG_LABELS = {
    original: "ORIGINAL",
    en: "ENGLISH",
    hi: "HINDI (हिन्दी)",
    te: "TELUGU (తెలుగు)",
    fr: "FRENCH (FRANÇAIS)",
  };
  if (dom.audioActiveLangBadge) {
    dom.audioActiveLangBadge.textContent = LANG_LABELS[activeLang] || activeLang.toUpperCase();
  }
  updateAudioTranslationDisplay(activeLang, LANG_LABELS);

  // E. Crime Event Timeline
  const timeline = report.timeline || [];
  if (dom.audioTimelineCountBadge) {
    dom.audioTimelineCountBadge.textContent = `${timeline.length} event${timeline.length === 1 ? "" : "s"}`;
  }

  if (dom.audioTimelineContainer) {
    if (timeline.length === 0) {
      dom.audioTimelineContainer.innerHTML = `<p class="muted" style="padding:1rem;">No distinct chronological events identified in transcript.</p>`;
    } else {
      let tHtml = `
        <div class="timeline-table-wrapper">
          <table class="timeline-table">
            <thead>
              <tr>
                <th style="width:72px;">Timestamp</th>
                <th style="width:40%;">Observed Event</th>
                <th>Transcript Excerpt</th>
              </tr>
            </thead>
            <tbody>
      `;
      timeline.forEach(item => {
        const tsSec = parseFloat(item.timestamp_seconds || 0).toFixed(1);
        const tsDisplay = item.timestamp_display || `${tsSec}s`;
        const estTag = item.is_estimated ? `<span class="badge badge-amber badge-xs" style="font-size:9px; padding:1px 3px; margin-left:4px;">est</span>` : "";
        tHtml += `
          <tr class="timeline-row" data-timestamp="${tsSec}">
            <td>
              <button type="button" class="timeline-ts-btn" data-timestamp="${tsSec}" title="Click to seek audio playback to ${tsDisplay}">
                <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
                <span>${escapeHtml(tsDisplay)}</span>
              </button>
              ${estTag}
            </td>
            <td style="color:var(--text-primary); font-weight:500;">
              ${escapeHtml(item.event_description || "")}
            </td>
            <td style="color:var(--text-secondary); font-style:italic;">
              "${escapeHtml(item.transcript_excerpt || "")}"
            </td>
          </tr>
        `;
      });
      tHtml += `
            </tbody>
          </table>
        </div>
      `;
      dom.audioTimelineContainer.innerHTML = tHtml;

      // Attach seek listeners to timeline rows and buttons
      dom.audioTimelineContainer.querySelectorAll(".timeline-ts-btn, .timeline-row").forEach(el => {
        el.addEventListener("click", () => {
          const row = el.closest(".timeline-row");
          const ts = parseFloat((row && row.dataset.timestamp) || el.dataset.timestamp || 0);
          if (!isNaN(ts) && dom.evidenceAudio) {
            dom.evidenceAudio.currentTime = ts;
            dom.evidenceAudio.play();
            dom.audioTimelineContainer.querySelectorAll(".timeline-row").forEach(r => r.style.background = "");
            if (row) row.style.background = "rgba(0, 240, 255, 0.12)";
          }
        });
      });
    }
  }
}

function clearAudioAnalysisFindings() {
  state.currentAudioAnalysis = null;
  state.currentAudioTranslations = null;
  if (dom.whisperLangBadge) dom.whisperLangBadge.style.display = "none";
  if (dom.audioSegmentCountBadge) dom.audioSegmentCountBadge.style.display = "none";
  if (dom.whisperContent) dom.whisperContent.innerHTML = `<p class="muted">Click 'Run Audio Transcription' to process speech audio.</p>`;
  if (dom.audioTranscriptContainer) dom.audioTranscriptContainer.style.display = "none";
  if (dom.audioSegmentsList) dom.audioSegmentsList.innerHTML = "";
  if (dom.audioStatusBadge) {
    dom.audioStatusBadge.textContent = "Ready";
    dom.audioStatusBadge.className = "badge badge-neutral badge-sm";
  }
  if (dom.audioStatDuration) dom.audioStatDuration.textContent = "—";
  if (dom.audioStatSr) dom.audioStatSr.textContent = "—";
  if (dom.audioStatChannels) dom.audioStatChannels.textContent = "1 (Mono)";
  if (dom.audioStatStatus) dom.audioStatStatus.textContent = "Ready";
  if (dom.audioCustodyEid) dom.audioCustodyEid.textContent = "—";
  if (dom.audioCustodyHash) dom.audioCustodyHash.textContent = "—";
  if (dom.audioIntelBadge) {
    dom.audioIntelBadge.textContent = "Pending";
    dom.audioIntelBadge.className = "badge badge-xs badge-slate";
  }
  if (dom.audioAiSummaryContent) {
    dom.audioAiSummaryContent.innerHTML = `<p class="muted">Transcribe audio to synthesize executive witness statement summary.</p>`;
  }
  if (dom.audioEventTypeBadge) {
    dom.audioEventTypeBadge.textContent = "Undetermined";
    dom.audioEventTypeBadge.className = "badge badge-slate badge-sm";
  }
  if (dom.audioEventTypeDetail) {
    dom.audioEventTypeDetail.textContent = "Pending audio transcription.";
  }
  if (dom.audioLocationText) {
    dom.audioLocationText.textContent = "Not specified";
  }
  if (dom.audioEntitiesContent) {
    dom.audioEntitiesContent.innerHTML = `<p class="muted">Entities mentioned (vehicles, persons, clothing, times) will be extracted from spoken statements.</p>`;
  }
  if (dom.audioSegmentsPlaceholder) {
    dom.audioSegmentsPlaceholder.style.display = "block";
  }
  if (dom.audioCustodyCase) dom.audioCustodyCase.textContent = "—";
  if (dom.audioCustodyFilename) dom.audioCustodyFilename.textContent = "—";
  if (dom.audioDetailFormat) dom.audioDetailFormat.textContent = "—";
  if (dom.audioDetailFilesize) dom.audioDetailFilesize.textContent = "—";
  if (dom.audioDetailUploaded) dom.audioDetailUploaded.textContent = "—";
  if (dom.audioActiveLangBadge) {
    dom.audioActiveLangBadge.textContent = "ORIGINAL";
  }
  if (dom.audioTranslationDisplay) {
    dom.audioTranslationDisplay.innerHTML = `<p class="muted">Translations into English, Hindi, Telugu, and French will appear after transcription.</p>`;
  }
  if (dom.audioTimelineCountBadge) {
    dom.audioTimelineCountBadge.textContent = "0 events";
  }
  if (dom.audioTimelineContainer) {
    dom.audioTimelineContainer.innerHTML = `<p class="muted" style="padding:1rem;">Chronological events extracted from audio transcript will appear here. Click any timestamp to seek playback.</p>`;
  }
  if (dom.audioChatResponseArea) {
    dom.audioChatResponseArea.innerHTML = `
      <div class="img-chat-placeholder" id="audio-chat-placeholder">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
        </svg>
        <p>Ask questions about this audio statement. Responses are strictly grounded in the verified transcript and forensic timeline.</p>
      </div>
    `;
  }
  if (dom.audioChatStatus) {
    dom.audioChatStatus.textContent = "Ready";
    dom.audioChatStatus.className = "badge badge-xs badge-emerald";
  }
}

function updateAudioTranslationDisplay(lang, labels = null) {
  if (!dom.audioTranslationDisplay) return;
  const LANG_LABELS = labels || {
    original: "ORIGINAL",
    en: "ENGLISH",
    hi: "HINDI (हिन्दी)",
    te: "TELUGU (తెలుగు)",
    fr: "FRENCH (FRANÇAIS)",
  };
  const trans = state.currentAudioTranslations ? state.currentAudioTranslations[lang] : null;
  if (typeof trans === "object" && trans !== null) {
    if (trans.status === "translation_unavailable") {
      dom.audioTranslationDisplay.innerHTML = `
        <div style="padding:10px 14px; border-radius:6px; background:rgba(234, 179, 8, 0.08); border:1px solid rgba(234, 179, 8, 0.25); color:var(--text-secondary); font-size:12px; line-height:1.5;">
          <div style="color:#eab308; font-weight:600; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
            <i class="fas fa-exclamation-triangle"></i> Translation Unavailable
          </div>
          <span>${escapeHtml(trans.explanation || "Machine translation was not generated.")}</span>
        </div>`;
      return;
    }
    if (trans.text) {
      dom.audioTranslationDisplay.innerHTML = `<p style="line-height:1.6; color:var(--text-primary); font-size:12.5px;">${escapeHtml(trans.text)}</p>`;
      return;
    }
  }
  if (typeof trans === "string" && trans.trim()) {
    dom.audioTranslationDisplay.innerHTML = `<p style="line-height:1.6; color:var(--text-primary); font-size:12.5px;">${escapeHtml(trans)}</p>`;
  } else {
    dom.audioTranslationDisplay.innerHTML = `<p class="muted">Translation for ${escapeHtml(LANG_LABELS[lang] || lang)} is not available.</p>`;
  }
}

function initAudioIntelligenceControls() {
  const LANG_LABELS = {
    original: "ORIGINAL",
    en: "ENGLISH",
    hi: "HINDI (हिन्दी)",
    te: "TELUGU (తెలుగు)",
    fr: "FRENCH (FRANÇAIS)",
  };

  if (dom.audioLangTabBtns) {
    dom.audioLangTabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        dom.audioLangTabBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const lang = btn.dataset.lang || "original";
        state.activeAudioLang = lang;
        if (dom.audioActiveLangBadge) {
          dom.audioActiveLangBadge.textContent = LANG_LABELS[lang] || lang.toUpperCase();
        }
        updateAudioTranslationDisplay(lang, LANG_LABELS);
      });
    });
  }

  if (dom.audioChatChips) {
    dom.audioChatChips.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip-btn");
      if (!chip) return;
      const prompt = chip.dataset.audioPrompt;
      if (prompt) {
        if (dom.audioChatInput) dom.audioChatInput.value = prompt;
        sendAudioChatMessage(prompt);
      }
    });
  }

  if (dom.audioChatForm) {
    dom.audioChatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = (dom.audioChatInput ? dom.audioChatInput.value : "").trim();
      if (val) sendAudioChatMessage(val);
    });
  }
}

async function sendAudioChatMessage(queryText) {
  const caseId = state.activeCaseId;
  const evidenceId = state.activeEvidenceId;
  if (!caseId || !evidenceId) {
    showToast("Please select an audio evidence item first.", "warning");
    return;
  }
  const query = (queryText || (dom.audioChatInput ? dom.audioChatInput.value : "")).trim();
  if (!query) return;

  if (dom.audioChatInput) dom.audioChatInput.value = "";
  if (dom.audioChatPlaceholder) dom.audioChatPlaceholder.style.display = "none";

  appendAudioChatBubble("user", query);

  if (dom.btnAudioChatSend) dom.btnAudioChatSend.disabled = true;
  if (dom.audioChatSendText) dom.audioChatSendText.style.display = "none";
  if (dom.audioChatSendSpinner) dom.audioChatSendSpinner.style.display = "inline-block";
  if (dom.audioChatStatus) {
    dom.audioChatStatus.textContent = "Analyzing…";
    dom.audioChatStatus.className = "badge badge-xs badge-amber";
  }

  try {
    const { ok, data } = await apiFetch(API.chatEvidence(caseId, evidenceId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      silent403: true,
    });

    if (ok && data && data.response) {
      appendAudioChatBubble("assistant", data.response);
      if (dom.audioChatStatus) {
        dom.audioChatStatus.textContent = "Ready";
        dom.audioChatStatus.className = "badge badge-xs badge-emerald";
      }
    } else {
      appendAudioChatBubble("error", data.error || "Unable to retrieve audio analysis response.");
      if (dom.audioChatStatus) {
        dom.audioChatStatus.textContent = "Error";
        dom.audioChatStatus.className = "badge badge-xs badge-crimson";
      }
    }
  } catch (err) {
    appendAudioChatBubble("error", `Network error: ${err.message}`);
    if (dom.audioChatStatus) {
      dom.audioChatStatus.textContent = "Error";
      dom.audioChatStatus.className = "badge badge-xs badge-crimson";
    }
  } finally {
    if (dom.btnAudioChatSend) dom.btnAudioChatSend.disabled = false;
    if (dom.audioChatSendText) dom.audioChatSendText.style.display = "inline-block";
    if (dom.audioChatSendSpinner) dom.audioChatSendSpinner.style.display = "none";
  }
}

function appendAudioChatBubble(type, payload) {
  if (!dom.audioChatResponseArea) return;
  const bubble = document.createElement("div");
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (type === "user") {
    bubble.className = "img-chat-bubble-user";
    bubble.innerHTML = `<div>${escapeHtml(payload)}</div><div class="img-chat-bubble-meta"><span>Investigator</span><span>${timeStr}</span></div>`;
  } else if (type === "error") {
    bubble.className = "img-chat-bubble-assistant";
    bubble.style.borderColor = "rgba(239, 68, 68, 0.4)";
    bubble.innerHTML = `<div style="color:#F87171;">⚠️ ${escapeHtml(payload)}</div><div class="img-chat-bubble-meta"><span>Error</span><span>${timeStr}</span></div>`;
  } else {
    bubble.className = "img-chat-bubble-assistant";
    const answer = typeof payload === "string" ? payload : (payload.answer || "");
    const evidenceList = (payload.supporting_evidence || []);
    const limitations = (payload.limitations || []);

    let evHtml = "";
    if (evidenceList.length > 0) {
      evHtml = `<div style="margin-top:6px; font-size:11px; color:var(--cyan-primary);"><strong>Cited Evidence:</strong> ` +
        evidenceList.map(e => `<code>${escapeHtml(e.evidence_id || state.activeEvidenceId)}</code> (${escapeHtml(e.detail || "")})`).join(", ") +
        `</div>`;
    }

    let limHtml = "";
    if (limitations.length > 0) {
      limHtml = `<div style="margin-top:4px; font-size:10.5px; color:var(--text-muted); font-style:italic;">Limitations: ` +
        limitations.map(l => escapeHtml(l)).join(" • ") +
        `</div>`;
    }

    bubble.innerHTML = `
      <div style="color:var(--text-primary); font-size:12px; line-height:1.5;">${escapeHtml(answer).replace(/\n/g, "<br/>")}</div>
      ${evHtml}
      ${limHtml}
      <div class="img-chat-bubble-meta">
        <span style="color:var(--cyan-primary);">Forensic Acoustic AI</span>
        <span>${timeStr}</span>
      </div>
    `;
  }

  dom.audioChatResponseArea.appendChild(bubble);
  dom.audioChatResponseArea.scrollTop = dom.audioChatResponseArea.scrollHeight;
}

/* ── Audio Subtabs Navigation ────────────────────────────────────────────── */
function initAudioSubtabs() {
  if (!dom.audioSubtabBtns || dom.audioSubtabBtns.length === 0) return;
  dom.audioSubtabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabName = btn.dataset.subtab;
      dom.audioSubtabBtns.forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      const targetPanelId = `audio-subtab-${tabName}`;
      document.querySelectorAll(".audio-subtab-panel").forEach(panel => {
        if (panel.id === targetPanelId) {
          panel.style.display = "flex";
          panel.classList.add("active");
        } else {
          panel.style.display = "none";
          panel.classList.remove("active");
        }
      });
    });
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   VIDEO ANALYSIS & KEYFRAME SAMPLING
══════════════════════════════════════════════════════════════════════════ */
async function runVideoAnalysis() {
  if (!state.activeCaseId) {
    showToast("Please select a case container first.", "warning");
    return;
  }

  // 1. Resolve target video artifact accurately
  let videoEid = null;
  const activeEv = state.evidence.find(e => e.evidence_id === state.activeEvidenceId);
  if (activeEv && activeEv.modality === "video") {
    videoEid = activeEv.evidence_id;
  } else if (dom.selectVideoEvidence && dom.selectVideoEvidence.value) {
    const selEv = state.evidence.find(e => e.evidence_id === dom.selectVideoEvidence.value && e.modality === "video");
    if (selEv) videoEid = selEv.evidence_id;
  }

  if (!videoEid) {
    const firstVid = state.evidence.find(e => e.modality === "video");
    if (firstVid) videoEid = firstVid.evidence_id;
  }

  if (!videoEid) {
    showToast("Please upload or select a video artifact from the Evidence Library.", "warning");
    return;
  }

  if (state.activeEvidenceId !== videoEid) {
    selectEvidence(videoEid, false);
  }

  // 2. Prevent accidental duplicate click / execution
  if (state.isVideoAnalyzing) {
    showToast("Video analysis is already in progress.", "info");
    return;
  }
  state.isVideoAnalyzing = true;

  const interval = parseFloat(dom.videoSampleInterval ? dom.videoSampleInterval.value : 1.0) || 1.0;
  const originalBtnText = dom.btnRunVideoAnalysis ? dom.btnRunVideoAnalysis.innerHTML : "Analyze Video";
  let elapsedSec = 0;
  if (dom.btnRunVideoAnalysis) {
    dom.btnRunVideoAnalysis.disabled = true;
    dom.btnRunVideoAnalysis.innerHTML = `<span class="spin-loader"></span> Analyzing Video (0s)…`;
  }
  const timer = setInterval(() => {
    elapsedSec += 1;
    if (dom.btnRunVideoAnalysis) {
      dom.btnRunVideoAnalysis.innerHTML = `<span class="spin-loader"></span> Analyzing Video (${elapsedSec}s)…`;
    }
  }, 1000);

  if (dom.videoStatusBadge) {
    dom.videoStatusBadge.textContent = "Sampling & Detecting…";
    dom.videoStatusBadge.className = "badge badge-amber badge-sm";
  }

  try {
    const { ok, status, data } = await apiFetch(
      API.analyzeVideo(state.activeCaseId, videoEid),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sample_interval_seconds: interval }),
      }
    );

    const backendStatus = (data && data.status) || (data && data.analysis && data.analysis.status) || (ok ? "completed" : "failed");
    const isSuccess = ok && data && backendStatus !== "failed";

    if (isSuccess) {
      const isPartial = backendStatus === "partial";
      if (isPartial) {
        showToast("Video frame sampling completed with partial results.", "warning");
        if (dom.videoStatusBadge) {
          dom.videoStatusBadge.textContent = "Analysis Partial";
          dom.videoStatusBadge.className = "badge badge-amber badge-sm";
        }
      } else {
        showToast("Video frame sampling and temporal RT-DETR detection completed.", "success");
        if (dom.videoStatusBadge) {
          dom.videoStatusBadge.textContent = "Video Analyzed";
          dom.videoStatusBadge.className = "badge badge-emerald badge-sm";
        }
      }
      const ev = state.evidence.find(e => e.evidence_id === videoEid);
      if (ev) {
        ev.analysis_json = data.analysis;
        ev.analysis_status = backendStatus;
      }

      renderVideoAnalysisFindings(data.analysis);
    } else {
      clearVideoAnalysisFindings();
      const ev = state.evidence.find(e => e.evidence_id === videoEid);
      if (ev) ev.analysis_status = "failed";
      const errDetail = (data && data.analysis && data.analysis.video && data.analysis.video.error)
        || (data && data.error)
        || `Error ${status}: Video analysis failed.`;

      if (dom.videoStatusBadge) {
        dom.videoStatusBadge.textContent = "Analysis Failed";
        dom.videoStatusBadge.className = "badge badge-crimson badge-sm";
      }
      dom.videoContent.innerHTML = `
        <div style="color:var(--crimson); font-size:12.5px; padding:12px; background:rgba(239,68,68,0.08); border-radius:6px; border:1px solid rgba(239,68,68,0.2);">
          <strong style="display:block; margin-bottom:4px;">Video Analysis Failed:</strong>
          ${escapeHtml(errDetail)}
          <div style="margin-top:10px; display:flex; gap:8px;">
            <button class="btn btn-sm btn-crimson" onclick="runVideoAnalysis()" style="font-size:11.5px; padding:4px 10px; cursor:pointer;">
              Retry Video Analysis
            </button>
            <button class="btn btn-sm btn-secondary" onclick="restoreSampleBaseline()" style="font-size:11.5px; padding:4px 10px; cursor:pointer;">
              Restore Sample Baseline
            </button>
          </div>
        </div>
      `;
      if (dom.videoTimelineContainer) dom.videoTimelineContainer.style.display = "none";
      showToast(errDetail, "error");
    }
  } catch (err) {
    clearVideoAnalysisFindings();
    const ev = state.evidence.find(e => e.evidence_id === videoEid);
    if (ev) ev.analysis_status = "failed";
    if (dom.videoStatusBadge) {
      dom.videoStatusBadge.textContent = "Analysis Failed";
      dom.videoStatusBadge.className = "badge badge-crimson badge-sm";
    }
    showToast(err.message || "Failed to execute video analysis.", "error");
  } finally {
    clearInterval(timer);
    if (dom.btnRunVideoAnalysis) {
      dom.btnRunVideoAnalysis.innerHTML = originalBtnText;
      dom.btnRunVideoAnalysis.disabled = false;
    }
    state.isVideoAnalyzing = false;
  }
}

function renderVideoAnalysisFindings(analysis) {
  if (!analysis) return;
  state.currentVideoAnalysis = analysis;

  const videoData = analysis.video || analysis;
  const videoMeta = videoData.video_metadata || analysis.video_metadata || {};
  const frames = videoData.sampled_frames || analysis.sampled_frames || [];
  const samplingParams = videoData.sampling_parameters || analysis.sampling_parameters || {};
  const sceneIntel = videoData.scene_intelligence || analysis.scene_intelligence || {};
  const visualSummary = videoData.visual_summary || analysis.visual_summary || {};
  const timeline = videoData.event_timeline || analysis.event_timeline || [];

  let totalObjects = 0;
  frames.forEach(f => {
    const objs = f.objects || f.detections || [];
    totalObjects += objs.length;
  });

  // Status Badge
  if (dom.videoStatusBadge) {
    if (videoData.status === "failed") {
      dom.videoStatusBadge.textContent = "Analysis Failed";
      dom.videoStatusBadge.className = "badge badge-crimson badge-sm";
    } else if (videoData.status === "partial" || analysis.status === "partial") {
      dom.videoStatusBadge.textContent = "Analysis Partial";
      dom.videoStatusBadge.className = "badge badge-amber badge-sm";
    } else if (frames.length > 0 && totalObjects > 0) {
      dom.videoStatusBadge.textContent = "Video Analyzed";
      dom.videoStatusBadge.className = "badge badge-emerald badge-sm";
    } else if (frames.length > 0 && totalObjects === 0) {
      dom.videoStatusBadge.textContent = "0 Objects Detected";
      dom.videoStatusBadge.className = "badge badge-cobalt badge-sm";
    } else {
      dom.videoStatusBadge.textContent = "No Frames";
      dom.videoStatusBadge.className = "badge badge-amber badge-sm";
    }
  }

  // Count Badge
  if (dom.videoCountBadge) {
    dom.videoCountBadge.style.display = "inline-flex";
    dom.videoCountBadge.textContent = `${totalObjects} detection${totalObjects === 1 ? "" : "s"} across ${frames.length} frame${frames.length === 1 ? "" : "s"}`;
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 1. SCENE INTELLIGENCE
  // ══════════════════════════════════════════════════════════════════════════
  const detectedObjs = sceneIntel.objects_detected || [];
  if (dom.videoObjectsDetectedContainer) {
    if (detectedObjs.length > 0) {
      let chipsHtml = "";
      detectedObjs.forEach(o => {
        const confPct = Math.round((o.confidence !== undefined ? o.confidence : 0) * 100);
        chipsHtml += `
          <span class="video-object-chip">
            <span class="chip-label">${escapeHtml(o.label)}</span>
            <span class="chip-count">×${o.count}</span>
            <span class="chip-conf">${confPct}%</span>
          </span>
        `;
      });
      dom.videoObjectsDetectedContainer.innerHTML = chipsHtml;
    } else {
      dom.videoObjectsDetectedContainer.innerHTML = `<p class="muted" style="font-size:11.5px; margin:0;">No objects detected above threshold.</p>`;
    }
  }
  if (dom.videoIntelObjectsCount) {
    dom.videoIntelObjectsCount.textContent = `${detectedObjs.length} class${detectedObjs.length === 1 ? "" : "es"}`;
  }

  // People count metrics
  const pInfo = sceneIntel.people_count || {};
  if (dom.videoPeoplePeak) dom.videoPeoplePeak.textContent = pInfo.peak !== undefined ? pInfo.peak : 0;
  if (dom.videoPeopleTotal) dom.videoPeopleTotal.textContent = pInfo.total !== undefined ? pInfo.total : 0;
  if (dom.videoPeopleAvg) dom.videoPeopleAvg.textContent = pInfo.average !== undefined ? pInfo.average : "0.0";
  if (dom.videoPeopleSummary) dom.videoPeopleSummary.textContent = pInfo.summary || "0 people detected across analyzed frames.";

  // Vehicle count metrics
  const VEHICLE_LABELS = new Set(["car", "truck", "bus", "motorcycle", "motorbike", "bicycle", "van", "suv", "vehicle"]);
  let vehiclePeak = 0;
  let vehicleTotal = 0;
  frames.forEach(f => {
    const objs = f.objects || f.detections || [];
    let frameVehicles = 0;
    objs.forEach(o => {
      const lbl = (o.label || "").toLowerCase();
      if (VEHICLE_LABELS.has(lbl)) {
        frameVehicles++;
        vehicleTotal++;
      }
    });
    if (frameVehicles > vehiclePeak) vehiclePeak = frameVehicles;
  });
  const vehicleAvg = frames.length > 0 ? (vehicleTotal / frames.length).toFixed(1) : "0.0";
  if (dom.videoVehiclesPeak) dom.videoVehiclesPeak.textContent = vehiclePeak;
  if (dom.videoVehiclesTotal) dom.videoVehiclesTotal.textContent = vehicleTotal;
  if (dom.videoVehiclesAvg) dom.videoVehiclesAvg.textContent = vehicleAvg;
  if (dom.videoVehiclesSummary) {
    dom.videoVehiclesSummary.textContent = `${vehicleTotal} vehicle detection${vehicleTotal === 1 ? "" : "s"} across ${frames.length} frame${frames.length === 1 ? "" : "s"} (peak of ${vehiclePeak} in a single frame).`;
  }

  // Sampled Keyframe Observations for Tab 1
  if (dom.videoFrameSummariesList) {
    if (frames.length > 0) {
      let fSumHtml = "";
      frames.forEach((f, idx) => {
        const ts = parseFloat(f.timestamp_seconds !== undefined ? f.timestamp_seconds : idx * 1.0).toFixed(1);
        const objs = f.objects || f.detections || [];
        const classCounts = {};
        objs.forEach(o => {
          const lbl = (o.label || "unknown").toLowerCase();
          classCounts[lbl] = (classCounts[lbl] || 0) + 1;
        });
        const tags = Object.entries(classCounts).map(([k, v]) => `${k} ×${v}`).join(" • ") || "No salient objects";
        fSumHtml += `
          <div class="video-frame-summary-item frame-summary-row" data-ts="${ts}">
            <div style="display:flex; align-items:center; gap:6px; min-width:0;">
              <span class="badge badge-cobalt badge-xs" style="font-family:var(--font-mono); font-size:10px;">${ts}s</span>
              <span style="font-size:11.5px; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(tags)}</span>
            </div>
            <span class="badge badge-slate badge-xs" style="margin-left:auto; font-size:10px;">${objs.length} item${objs.length === 1 ? "" : "s"}</span>
          </div>
        `;
      });
      dom.videoFrameSummariesList.innerHTML = fSumHtml;
      dom.videoFrameSummariesList.querySelectorAll(".frame-summary-row").forEach(row => {
        row.addEventListener("click", () => {
          const ts = parseFloat(row.dataset.ts);
          if (!isNaN(ts) && dom.evidenceVideo) {
            dom.evidenceVideo.currentTime = ts;
            updateVideoOverlay(ts);
          }
        });
      });
    } else {
      dom.videoFrameSummariesList.innerHTML = `<p class="muted" style="font-size:11px; margin:0;">No frame summaries available.</p>`;
    }
  }

  // Location / Scene type
  const sceneType = sceneIntel.scene_type || "Undetermined";
  const sceneConf = Math.round((sceneIntel.scene_type_confidence || 0) * 100);
  if (dom.videoSceneName) dom.videoSceneName.textContent = sceneType;
  if (dom.videoSceneConf) dom.videoSceneConf.textContent = `${sceneConf}%`;
  if (dom.videoSceneBasis) dom.videoSceneBasis.textContent = sceneIntel.scene_type_basis || "Evidence inference pending.";
  if (dom.videoSceneTypeBadge) {
    const isUndet = sceneType.toLowerCase().includes("undetermined");
    dom.videoSceneTypeBadge.textContent = isUndet ? "Undetermined" : "Analyzed";
    dom.videoSceneTypeBadge.className = `badge badge-xs ${isUndet ? "badge-slate" : "badge-emerald"}`;
  }

  // Observable Actions
  const actions = sceneIntel.observable_actions || [];
  if (dom.videoObservableActionsList) {
    if (actions.length > 0) {
      let actHtml = "";
      actions.forEach(act => {
        actHtml += `
          <li class="video-action-item">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
            <span>${escapeHtml(act)}</span>
          </li>
        `;
      });
      dom.videoObservableActionsList.innerHTML = actHtml;
    } else {
      dom.videoObservableActionsList.innerHTML = `<li class="video-action-item muted">No observable human or vehicular actions detected</li>`;
    }
  }

  if (dom.videoSceneIntelContent) dom.videoSceneIntelContent.style.display = "block";
  if (dom.videoSceneIntelPlaceholder) dom.videoSceneIntelPlaceholder.style.display = "none";

  // ══════════════════════════════════════════════════════════════════════════
  // 2. AI VISUAL SUMMARY
  // ══════════════════════════════════════════════════════════════════════════
  if (dom.videoSummaryNarrative) {
    dom.videoSummaryNarrative.textContent = visualSummary.summary || "Visual summary pending.";
  }

  // Direct observations
  const directObs = visualSummary.direct_observations || [];
  if (dom.videoDirectObservationsList) {
    if (directObs.length > 0) {
      let dHtml = "";
      directObs.forEach(obs => {
        dHtml += `
          <li class="video-obs-item">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>${escapeHtml(obs)}</span>
          </li>
        `;
      });
      dom.videoDirectObservationsList.innerHTML = dHtml;
    } else {
      dom.videoDirectObservationsList.innerHTML = `<li class="video-obs-item muted">No verified visual observations recorded.</li>`;
    }
  }

  // AI Interpretations
  const aiInterps = visualSummary.ai_interpretations || [];
  if (dom.videoAiInterpretationsList) {
    if (aiInterps.length > 0) {
      let iHtml = "";
      aiInterps.forEach(interp => {
        iHtml += `
          <li class="video-interp-item">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            <span>${escapeHtml(interp)}</span>
          </li>
        `;
      });
      dom.videoAiInterpretationsList.innerHTML = iHtml;
    } else {
      dom.videoAiInterpretationsList.innerHTML = `<li class="video-interp-item muted">No AI interpretations generated.</li>`;
    }
  }

  // Uncertainty Details
  if (dom.videoUncertaintyDetails) {
    dom.videoUncertaintyDetails.textContent = visualSummary.uncertainty_details || "Standard forensic video sampling limitations apply.";
  }

  // Summary Activity Status badge
  if (dom.videoSummaryStatus) {
    const sText = (visualSummary.summary || "").toLowerCase();
    if (sText.includes("suspicious") || sText.includes("incident") || sText.includes("altercation")) {
      dom.videoSummaryStatus.textContent = "Potential Incident";
      dom.videoSummaryStatus.className = "badge badge-amber badge-xs";
    } else {
      dom.videoSummaryStatus.textContent = "Routine Activity";
      dom.videoSummaryStatus.className = "badge badge-emerald badge-xs";
    }
  }

  if (dom.videoSummaryContent) dom.videoSummaryContent.style.display = "block";
  if (dom.videoSummaryPlaceholder) dom.videoSummaryPlaceholder.style.display = "none";

  // ══════════════════════════════════════════════════════════════════════════
  // 3. EVENT TIMELINE
  // ══════════════════════════════════════════════════════════════════════════
  const timelineItems = (timeline && timeline.length > 0) ? timeline : frames.map((f, idx) => {
    const ts = parseFloat(f.timestamp_seconds !== undefined ? f.timestamp_seconds : idx * 1.0).toFixed(1);
    const objs = f.objects || f.detections || [];
    const classCounts = {};
    objs.forEach(o => {
      const lbl = o.label || "unknown";
      classCounts[lbl] = (classCounts[lbl] || 0) + 1;
    });
    const detPills = Object.entries(classCounts).map(([k, v]) => `${k}: ${v}`);
    return {
      timestamp_seconds: parseFloat(ts),
      timestamp_display: `${ts}s`,
      frame_index: f.frame_index !== undefined ? f.frame_index : idx,
      primary_activity: objs.length > 0 ? `${objs.length} entity detection${objs.length === 1 ? "" : "s"}` : "Clear interval",
      description: objs.length > 0 ? `Keyframe snapshot at ${ts}s recording ${detPills.join(", ")}.` : `No salient foreground objects at ${ts}s.`,
      detection_count: objs.length,
      detections: detPills,
    };
  });

  if (timelineItems.length > 0) {
    if (dom.videoTimelineContainer) dom.videoTimelineContainer.style.display = "block";
    if (dom.videoTimelinePlaceholder) dom.videoTimelinePlaceholder.style.display = "none";
    if (dom.videoTimelineCountBadge) dom.videoTimelineCountBadge.textContent = `${timelineItems.length} frame${timelineItems.length === 1 ? "" : "s"}`;

    let timelineHtml = "";
    timelineItems.forEach(item => {
      const ts = parseFloat(item.timestamp_seconds !== undefined ? item.timestamp_seconds : 0).toFixed(1);
      const displayTs = item.timestamp_display || `${ts}s`;
      const primaryAct = item.primary_activity || "Temporal keyframe";
      const desc = item.description || "";
      const pills = item.detections || [];

      let chipsHtml = "";
      pills.forEach(p => {
        chipsHtml += `<span class="badge badge-slate badge-xs" style="font-family:var(--font-mono);">${escapeHtml(p)}</span>`;
      });

      timelineHtml += `
        <div class="video-timeline-entry frame-row" data-ts="${ts}">
          <div class="entry-header">
            <span class="badge badge-cobalt badge-xs entry-ts" style="font-family:var(--font-mono);">${escapeHtml(displayTs)}</span>
            <span class="entry-activity">${escapeHtml(primaryAct)}</span>
            <span class="muted" style="font-size:11px; margin-left:auto;">${item.detection_count || 0} item${(item.detection_count || 0) === 1 ? "" : "s"}</span>
          </div>
          <div class="entry-desc">${escapeHtml(desc)}</div>
          ${chipsHtml ? `<div class="entry-chips">${chipsHtml}</div>` : ""}
        </div>
      `;
    });

    if (dom.videoFramesList) {
      dom.videoFramesList.innerHTML = timelineHtml;
      dom.videoFramesList.querySelectorAll(".frame-row").forEach(row => {
        row.addEventListener("click", () => {
          const ts = parseFloat(row.dataset.ts);
          if (!isNaN(ts) && dom.evidenceVideo) {
            dom.evidenceVideo.currentTime = ts;
            updateVideoOverlay(ts);
          }
        });
      });
    }
  } else {
    if (dom.videoTimelineContainer) dom.videoTimelineContainer.style.display = "none";
    if (dom.videoTimelinePlaceholder) dom.videoTimelinePlaceholder.style.display = "flex";
  }

  // Summary metadata content (for backwards compatibility)
  const dur = videoMeta.duration_seconds || videoMeta.duration;
  const durStr = dur ? `${parseFloat(dur).toFixed(1)}s` : "";
  const fpsStr = videoMeta.fps ? `${videoMeta.fps} fps` : "";
  const resStr = (videoMeta.width && videoMeta.height) ? `${videoMeta.width}×${videoMeta.height}` : "";
  const metaInfo = [durStr, fpsStr, resStr].filter(Boolean).join(" • ");
  const intervalUsed = samplingParams.sample_interval_seconds || 1.0;

  if (dom.videoContent) {
    dom.videoContent.innerHTML = `
      <p style="font-size:12.5px; color:var(--text-primary); margin-bottom:4px;">
        Sampled <strong>${frames.length}</strong> temporal frames at <strong>${intervalUsed}s</strong> intervals${metaInfo ? ` (${metaInfo})` : ""}.
      </p>
    `;
  }

  // Render overlay for current playback position
  updateVideoOverlay();
}

function clearVideoAnalysisFindings() {
  state.currentVideoAnalysis = null;
  state.activeVideoTimestamp = null;
  if (dom.videoCountBadge) dom.videoCountBadge.style.display = "none";
  if (dom.videoStatusBadge) {
    dom.videoStatusBadge.textContent = "Ready";
    dom.videoStatusBadge.className = "badge badge-neutral badge-sm";
  }
  if (dom.videoBboxCanvas) {
    const ctx = dom.videoBboxCanvas.getContext("2d");
    ctx.clearRect(0, 0, dom.videoBboxCanvas.width, dom.videoBboxCanvas.height);
  }

  // Reset Scene Intelligence
  if (dom.videoSceneIntelContent) dom.videoSceneIntelContent.style.display = "none";
  if (dom.videoSceneIntelPlaceholder) dom.videoSceneIntelPlaceholder.style.display = "flex";
  if (dom.videoSceneTypeBadge) {
    dom.videoSceneTypeBadge.textContent = "Awaiting Analysis";
    dom.videoSceneTypeBadge.className = "badge badge-cobalt badge-xs";
  }
  if (dom.videoObjectsDetectedContainer) dom.videoObjectsDetectedContainer.innerHTML = "";
  if (dom.videoIntelObjectsCount) dom.videoIntelObjectsCount.textContent = "0 items";
  if (dom.videoPeoplePeak) dom.videoPeoplePeak.textContent = "0";
  if (dom.videoPeopleTotal) dom.videoPeopleTotal.textContent = "0";
  if (dom.videoPeopleAvg) dom.videoPeopleAvg.textContent = "0.0";
  if (dom.videoPeopleSummary) dom.videoPeopleSummary.textContent = "0 people detected across analyzed frames.";
  if (dom.videoVehiclesPeak) dom.videoVehiclesPeak.textContent = "0";
  if (dom.videoVehiclesTotal) dom.videoVehiclesTotal.textContent = "0";
  if (dom.videoVehiclesAvg) dom.videoVehiclesAvg.textContent = "0.0";
  if (dom.videoVehiclesSummary) dom.videoVehiclesSummary.textContent = "0 vehicles detected across analyzed frames.";
  if (dom.videoFrameSummariesList) dom.videoFrameSummariesList.innerHTML = "";
  if (dom.videoSceneName) dom.videoSceneName.textContent = "Undetermined";
  if (dom.videoSceneConf) dom.videoSceneConf.textContent = "0%";
  if (dom.videoSceneBasis) dom.videoSceneBasis.textContent = "Awaiting video analysis.";
  if (dom.videoObservableActionsList) dom.videoObservableActionsList.innerHTML = "";

  // Reset AI Visual Summary
  if (dom.videoSummaryContent) dom.videoSummaryContent.style.display = "none";
  if (dom.videoSummaryPlaceholder) dom.videoSummaryPlaceholder.style.display = "flex";
  if (dom.videoSummaryNarrative) dom.videoSummaryNarrative.textContent = "";
  if (dom.videoDirectObservationsList) dom.videoDirectObservationsList.innerHTML = "";
  if (dom.videoAiInterpretationsList) dom.videoAiInterpretationsList.innerHTML = "";
  if (dom.videoUncertaintyDetails) dom.videoUncertaintyDetails.textContent = "";

  // Reset Event Timeline
  if (dom.videoTimelineContainer) dom.videoTimelineContainer.style.display = "none";
  if (dom.videoTimelinePlaceholder) dom.videoTimelinePlaceholder.style.display = "flex";
  if (dom.videoTimelineCountBadge) dom.videoTimelineCountBadge.textContent = "0 frames";
  if (dom.videoFramesList) dom.videoFramesList.innerHTML = "";
}

function initVideoSubtabs() {
  const btns = document.querySelectorAll(".video-tab-btn, .video-subtab-btn");
  const panelIntel = document.getElementById("video-tab-panel-intel");
  const panelSummary = document.getElementById("video-tab-panel-summary");
  const panelTimeline = document.getElementById("video-tab-panel-timeline");

  if (!btns.length) return;

  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.dataset.vidTab || btn.dataset.vidSubtab;
      btns.forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      if (panelIntel) panelIntel.style.display = (targetTab === "intel" || targetTab === "both") ? "block" : "none";
      if (panelSummary) panelSummary.style.display = targetTab === "summary" ? "block" : "none";
      if (panelTimeline) panelTimeline.style.display = targetTab === "timeline" ? "block" : "none";
    });
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   MULTIMODAL EVIDENCE FUSION
══════════════════════════════════════════════════════════════════════════ */
async function runFusionAnalysis() {
  if (!state.activeCaseId) {
    showToast("Please select an active case container before running fusion.", "warning");
    return;
  }

  dom.btnRunFusion.disabled = true;
  dom.fusionStatusBadge.textContent = "Synthesizing Cross-Modal Truth…";
  dom.fusionStatusBadge.className = "badge badge-amber badge-sm";

  const { ok, status, data } = await apiFetch(
    API.analyzeFusion(state.activeCaseId),
    { method: "POST" }
  );

  dom.btnRunFusion.disabled = false;

  if (ok) {
    showToast("Multimodal evidence fusion synthesis completed.", "success");
    dom.fusionStatusBadge.textContent = "Synthesis Complete";
    dom.fusionStatusBadge.className = "badge badge-emerald badge-sm";

    renderFusionFindings(data.fusion);
  } else {
    dom.fusionStatusBadge.textContent = "Synthesis Failed";
    dom.fusionStatusBadge.className = "badge badge-crimson badge-sm";
    showToast(data.error || `Error ${status}: Fusion failed.`, "error");
  }
}

function renderFusionFindings(fusion) {
  if (!fusion) return;

  // Coverage
  const cov = fusion.modality_coverage || {};
  const imgTotal = cov.image_count ?? cov.image?.total ?? 0;
  const imgAnalyzed = cov.analyzed_image_count ?? cov.image?.analyzed ?? 0;
  const audTotal = cov.audio_count ?? cov.audio?.total ?? 0;
  const audAnalyzed = cov.analyzed_audio_count ?? cov.audio?.analyzed ?? 0;
  const vidTotal = cov.video_count ?? cov.video?.total ?? 0;
  const vidAnalyzed = cov.analyzed_video_count ?? cov.video?.analyzed ?? 0;

  dom.covImgBadge.textContent = `Image: ${imgTotal} (${imgAnalyzed} analyzed)`;
  dom.covAudBadge.textContent = `Audio: ${audTotal} (${audAnalyzed} analyzed)`;
  dom.covVidBadge.textContent = `Video: ${vidTotal} (${vidAnalyzed} analyzed)`;

  dom.covImgBadge.className = `badge badge-xs ${imgAnalyzed > 0 ? "badge-emerald" : "badge-slate"}`;
  dom.covAudBadge.className = `badge badge-xs ${audAnalyzed > 0 ? "badge-emerald" : "badge-slate"}`;
  dom.covVidBadge.className = `badge badge-xs ${vidAnalyzed > 0 ? "badge-emerald" : "badge-slate"}`;

  const totalEv = fusion.total_evidence_items ?? fusion.evidence_count ?? 0;
  dom.fusionScopeSummary.textContent = `${fusion.case_name || state.activeCaseId} · ${totalEv} evidence items`;

  // Corroborations
  const corrob = fusion.cross_modal_corroborations || fusion.cross_modal_associations || [];
  dom.fusionAssocCount.style.display = "inline-flex";
  dom.fusionAssocCount.textContent = `${corrob.length} match${corrob.length === 1 ? "" : "es"}`;

  if (corrob.length > 0) {
    let corHtml = `<div style="display:flex; flex-direction:column; gap:8px;">`;
    corrob.forEach(c => {
      const entityLabel = (c.entity || c.category || "Entity Corroboration").toUpperCase();
      const mods = Array.isArray(c.modalities_involved) ? ` [${c.modalities_involved.join(", ")}]` : "";
      corHtml += `
        <div style="padding:8px 10px; background:rgba(16, 185, 129, 0.05); border:1px solid rgba(16, 185, 129, 0.2); border-radius:4px;">
          <div style="font-weight:600; color:#34D399; font-size:12px; margin-bottom:2px;">${escapeHtml(entityLabel + mods)}</div>
          <p style="font-size:11.5px; color:var(--text-secondary);">${escapeHtml(c.observation || c.description || "Corroborated across multiple evidence modalities.")}</p>
        </div>
      `;
    });
    corHtml += `</div>`;
    dom.fusionAssociationsContent.innerHTML = corHtml;
  } else {
    dom.fusionAssociationsContent.innerHTML = `<p class="muted">No direct cross-modal entities corroborated across the current evidence artifacts.</p>`;
  }

  // Temporal alignments
  const temporal = fusion.temporal_alignments || fusion.temporal_associations || [];
  dom.fusionTemporalCount.style.display = "inline-flex";
  dom.fusionTemporalCount.textContent = `${temporal.length} alignment${temporal.length === 1 ? "" : "s"}`;

  if (temporal.length > 0) {
    let tHtml = `<div style="display:flex; flex-direction:column; gap:6px;">`;
    temporal.forEach(t => {
      const timeStr = t.timestamp || (Array.isArray(t.audio_timestamp_range) ? `${t.audio_timestamp_range[0]}s - ${t.audio_timestamp_range[1]}s` : "Timestamp");
      tHtml += `
        <div style="padding:6px 8px; background:rgba(59, 130, 246, 0.05); border-radius:4px;">
          <span class="badge badge-cobalt badge-xs">${escapeHtml(timeStr)}</span>
          <span style="font-size:11.5px; color:var(--text-secondary); margin-left:6px;">${escapeHtml(t.description || "Temporal correlation")}</span>
        </div>
      `;
    });
    tHtml += `</div>`;
    dom.fusionTemporalContent.innerHTML = tHtml;
  } else {
    dom.fusionTemporalContent.innerHTML = `<p class="muted">No synchronous audio-video events aligned in timeline.</p>`;
  }

  // Contradictions
  const conflicts = fusion.divergences_and_contradictions || fusion.potential_contradictions || [];
  dom.fusionConflictCount.style.display = "inline-flex";
  dom.fusionConflictCount.textContent = `${conflicts.length} flagged`;

  if (conflicts.length > 0) {
    let cHtml = `<div style="display:flex; flex-direction:column; gap:6px;">`;
    conflicts.forEach(cf => {
      cHtml += `
        <div style="padding:8px 10px; background:rgba(239, 68, 68, 0.05); border:1px solid rgba(239, 68, 68, 0.2); border-radius:4px;">
          <div style="font-weight:600; color:#F87171; font-size:12px;">Flagged Inconsistency</div>
          <p style="font-size:11.5px; color:var(--text-secondary);">${escapeHtml(cf.divergence || cf.explanation || cf.description || "Potential observational contradiction detected.")}</p>
        </div>
      `;
    });
    cHtml += `</div>`;
    dom.fusionContradictionsContent.innerHTML = cHtml;
  } else {
    dom.fusionContradictionsContent.innerHTML = `<p class="muted">No observational contradictions or scene divergences detected across analyzed sources.</p>`;
  }

  // Questions / Gaps
  const gaps = fusion.unresolved_investigative_questions || fusion.unresolved_questions || [];
  if (gaps.length > 0) {
    let gHtml = `<ul style="padding-left:1.2rem; color:var(--text-secondary); font-size:11.5px; display:flex; flex-direction:column; gap:4px;">`;
    gaps.forEach(g => {
      gHtml += `<li>${escapeHtml(g)}</li>`;
    });
    gHtml += `</ul>`;
    dom.fusionQuestionsContent.innerHTML = gHtml;
  } else {
    dom.fusionQuestionsContent.innerHTML = `<p class="muted">All available evidentiary channels have been processed.</p>`;
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   3D SPATIAL SCENE RECONSTRUCTION (Three.js)
══════════════════════════════════════════════════════════════════════════ */
const scene3dState = {
  scene: null,
  camera: null,
  renderer: null,
  controls: null,
  objectsGroup: null,
  gridHelper: null,
  selectionBracket: null,
  rawObjects: [],
  selectedObjectId: null,
  showGrid: true,
  showLabels: true,
  minConfidence: 0.30,
  isInitialized: false,
};

const CATEGORY_MARKERS = {
  person:       { family: "person",     icon: "👤", color: 0x10B981, hex: "#10B981" },
  pedestrian:   { family: "person",     icon: "👤", color: 0x10B981, hex: "#10B981" },
  cyclist:      { family: "person",     icon: "👤", color: 0x10B981, hex: "#10B981" },
  man:          { family: "person",     icon: "👤", color: 0x10B981, hex: "#10B981" },
  woman:        { family: "person",     icon: "👤", color: 0x10B981, hex: "#10B981" },
  car:          { family: "vehicle",    icon: "🚗", color: 0x3B82F6, hex: "#3B82F6" },
  vehicle:      { family: "vehicle",    icon: "🚗", color: 0x3B82F6, hex: "#3B82F6" },
  truck:        { family: "vehicle",    icon: "🚚", color: 0x3B82F6, hex: "#3B82F6" },
  bus:          { family: "vehicle",    icon: "🚌", color: 0x3B82F6, hex: "#3B82F6" },
  van:          { family: "vehicle",    icon: "🚐", color: 0x3B82F6, hex: "#3B82F6" },
  motorcycle:   { family: "motorcycle", icon: "🏍️", color: 0x06B6D4, hex: "#06B6D4" },
  motorbike:    { family: "motorcycle", icon: "🏍️", color: 0x06B6D4, hex: "#06B6D4" },
  bicycle:      { family: "motorcycle", icon: "🚲", color: 0x06B6D4, hex: "#06B6D4" },
  bike:         { family: "motorcycle", icon: "🚲", color: 0x06B6D4, hex: "#06B6D4" },
  chair:        { family: "furniture",  icon: "🪑", color: 0xD97706, hex: "#D97706" },
  couch:        { family: "furniture",  icon: "🛋️", color: 0xD97706, hex: "#D97706" },
  sofa:         { family: "furniture",  icon: "🛋️", color: 0xD97706, hex: "#D97706" },
  table:        { family: "furniture",  icon: "🪑", color: 0xD97706, hex: "#D97706" },
  bed:          { family: "furniture",  icon: "🛏️", color: 0xD97706, hex: "#D97706" },
  bench:        { family: "furniture",  icon: "🪑", color: 0xD97706, hex: "#D97706" },
  desk:         { family: "furniture",  icon: "🪑", color: 0xD97706, hex: "#D97706" },
  furniture:    { family: "furniture",  icon: "🪑", color: 0xD97706, hex: "#D97706" },
  backpack:     { family: "bag",        icon: "🎒", color: 0xF59E0B, hex: "#F59E0B" },
  bag:          { family: "bag",        icon: "👜", color: 0xF59E0B, hex: "#F59E0B" },
  handbag:      { family: "bag",        icon: "👜", color: 0xF59E0B, hex: "#F59E0B" },
  suitcase:     { family: "bag",        icon: "🧳", color: 0xF59E0B, hex: "#F59E0B" },
  bottle:       { family: "bottle",     icon: "🍾", color: 0x22C55E, hex: "#22C55E" },
  cup:          { family: "bottle",     icon: "🥤", color: 0x22C55E, hex: "#22C55E" },
  glass:        { family: "bottle",     icon: "🍷", color: 0x22C55E, hex: "#22C55E" },
  "wine glass": { family: "bottle",     icon: "🍷", color: 0x22C55E, hex: "#22C55E" },
  can:          { family: "bottle",     icon: "🥫", color: 0x22C55E, hex: "#22C55E" },
  knife:        { family: "threat",     icon: "⚠️", color: 0xEF4444, hex: "#EF4444" },
  weapon:       { family: "threat",     icon: "⚠️", color: 0xEF4444, hex: "#EF4444" },
  gun:          { family: "threat",     icon: "⚠️", color: 0xEF4444, hex: "#EF4444" },
  pistol:       { family: "threat",     icon: "⚠️", color: 0xEF4444, hex: "#EF4444" },
  scissors:     { family: "threat",     icon: "⚠️", color: 0xEF4444, hex: "#EF4444" },
  laptop:       { family: "device",     icon: "💻", color: 0x8B5CF6, hex: "#8B5CF6" },
  "cell phone": { family: "device",     icon: "📱", color: 0x8B5CF6, hex: "#8B5CF6" },
  tv:           { family: "device",     icon: "📺", color: 0x8B5CF6, hex: "#8B5CF6" },
  "traffic light":{ family: "signage",  icon: "🚦", color: 0xEC4899, hex: "#EC4899" },
  "stop sign":  { family: "signage",    icon: "🛑", color: 0xEC4899, hex: "#EC4899" },
};

function createBillboardSprite(text, hexStr) {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");

  ctx.clearRect(0, 0, 256, 64);

  // Background rounded rectangle badge
  ctx.fillStyle = "rgba(7, 12, 22, 0.88)";
  ctx.strokeStyle = hexStr || "#00F0FF";
  ctx.lineWidth = 3;
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(4, 4, 248, 56, 12);
  } else {
    ctx.rect(4, 4, 248, 56);
  }
  ctx.fill();
  ctx.stroke();

  // Text
  ctx.fillStyle = "#FFFFFF";
  ctx.font = "bold 20px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 128, 32);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const spriteMat = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
  });
  const sprite = new THREE.Sprite(spriteMat);
  sprite.scale.set(2.0, 0.5, 1.0);
  return sprite;
}

function createProceduralMarker(obj, colHex) {
  const cat = (obj.category || obj.label || "generic").toLowerCase();
  const meta = CATEGORY_MARKERS[cat] || { family: "generic", hex: "#94A3B8" };
  const markerType = obj.marker_type || meta.family;

  const group = new THREE.Group();
  group.name = obj.object_id;

  const mat = new THREE.MeshStandardMaterial({
    color: colHex,
    roughness: 0.32,
    metalness: 0.22,
    transparent: true,
    opacity: 0.92,
  });

  const wireMat = new THREE.LineBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.35,
  });

  const accentMat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    transparent: true,
    opacity: 0.7,
  });

  function addPart(geo, posX = 0, posY = 0, posZ = 0, rotX = 0, rotY = 0, rotZ = 0, customMat = mat, withWire = true) {
    const mesh = new THREE.Mesh(geo, customMat);
    mesh.position.set(posX, posY, posZ);
    if (rotX || rotY || rotZ) mesh.rotation.set(rotX, rotY, rotZ);
    mesh.userData = obj;
    group.add(mesh);

    if (withWire) {
      const edges = new THREE.EdgesGeometry(geo);
      const wire = new THREE.LineSegments(edges, wireMat);
      wire.position.copy(mesh.position);
      wire.rotation.copy(mesh.rotation);
      wire.userData = obj;
      group.add(wire);
    }
    return mesh;
  }

  // Ground beacon disc for all objects
  const groundRingGeo = new THREE.RingGeometry(0.35, 0.48, 16);
  addPart(groundRingGeo, 0, 0.02, 0, -Math.PI / 2, 0, 0, accentMat, false);

  let topY = 1.0;

  switch (markerType) {
    case "person": {
      // Stylized Person: Tapered torso + sphere head
      addPart(new THREE.CylinderGeometry(0.2, 0.32, 0.95, 12), 0, 0.68, 0);
      addPart(new THREE.SphereGeometry(0.26, 16, 12), 0, 1.3, 0);
      topY = 1.6;
      break;
    }
    case "vehicle": {
      // Stylized Automobile: Chassis + upper cabin + 4 wheels
      addPart(new THREE.BoxGeometry(2.1, 0.44, 1.2), 0, 0.36, 0);
      addPart(new THREE.BoxGeometry(1.2, 0.42, 0.95), -0.1, 0.78, 0);
      const wheelGeo = new THREE.CylinderGeometry(0.2, 0.2, 0.12, 12);
      addPart(wheelGeo, 0.7, 0.2, 0.62, 0, 0, Math.PI / 2);
      addPart(wheelGeo, -0.7, 0.2, 0.62, 0, 0, Math.PI / 2);
      addPart(wheelGeo, 0.7, 0.2, -0.62, 0, 0, Math.PI / 2);
      addPart(wheelGeo, -0.7, 0.2, -0.62, 0, 0, Math.PI / 2);
      topY = 1.2;
      break;
    }
    case "motorcycle": {
      // Two-Wheeler: 2 vertical toruses + connecting spine + handlebar + seat
      const wheelGeo = new THREE.TorusGeometry(0.34, 0.05, 8, 16);
      addPart(wheelGeo, 0, 0.35, 0.62, 0, Math.PI / 2, 0);
      addPart(wheelGeo, 0, 0.35, -0.62, 0, Math.PI / 2, 0);
      addPart(new THREE.CylinderGeometry(0.04, 0.04, 1.25, 8), 0, 0.38, 0, Math.PI / 2, 0, 0);
      addPart(new THREE.BoxGeometry(0.65, 0.08, 0.12), 0, 0.72, 0.42);
      addPart(new THREE.BoxGeometry(0.22, 0.08, 0.32), 0, 0.58, -0.15);
      topY = 1.0;
      break;
    }
    case "furniture": {
      // Chair / Table: Base horizontal plate + backrest + 4 post legs
      addPart(new THREE.BoxGeometry(0.9, 0.12, 0.9), 0, 0.44, 0);
      addPart(new THREE.BoxGeometry(0.9, 0.7, 0.1), 0, 0.85, -0.4);
      const legGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.44, 8);
      addPart(legGeo, 0.38, 0.22, 0.38);
      addPart(legGeo, -0.38, 0.22, 0.38);
      addPart(legGeo, 0.38, 0.22, -0.38);
      addPart(legGeo, -0.38, 0.22, -0.38);
      topY = 1.35;
      break;
    }
    case "bag": {
      // Backpack / Duffel: Rounded main pack + front pouch + top strap
      addPart(new THREE.BoxGeometry(0.65, 0.82, 0.45), 0, 0.44, 0);
      addPart(new THREE.BoxGeometry(0.48, 0.42, 0.14), 0, 0.34, 0.24);
      addPart(new THREE.TorusGeometry(0.12, 0.03, 6, 12, Math.PI), 0, 0.86, 0);
      topY = 1.1;
      break;
    }
    case "bottle": {
      // Container / Bottle: Main cylinder + neck + cap
      addPart(new THREE.CylinderGeometry(0.18, 0.18, 0.62, 12), 0, 0.34, 0);
      addPart(new THREE.CylinderGeometry(0.07, 0.16, 0.24, 12), 0, 0.74, 0);
      addPart(new THREE.CylinderGeometry(0.08, 0.08, 0.08, 12), 0, 0.88, 0);
      topY = 1.1;
      break;
    }
    case "threat": {
      // Tactical Threat / Weapon: Octahedron diamond + vertical beam
      addPart(new THREE.OctahedronGeometry(0.45), 0, 0.82, 0);
      addPart(new THREE.CylinderGeometry(0.02, 0.02, 0.8, 8), 0, 0.4, 0, 0, 0, 0, accentMat);
      topY = 1.4;
      break;
    }
    case "device": {
      // Electronic device / Laptop: Base plate + angled screen
      addPart(new THREE.BoxGeometry(0.85, 0.05, 0.65), 0, 0.08, 0);
      addPart(new THREE.BoxGeometry(0.85, 0.54, 0.04), 0, 0.34, -0.25, -0.3, 0, 0);
      topY = 0.9;
      break;
    }
    case "signage": {
      // Pole + signal head
      addPart(new THREE.CylinderGeometry(0.05, 0.05, 1.7, 8), 0, 0.85, 0);
      addPart(new THREE.BoxGeometry(0.38, 0.75, 0.32), 0, 1.42, 0);
      topY = 1.95;
      break;
    }
    default: {
      // Hexagonal beveled prism
      addPart(new THREE.CylinderGeometry(0.42, 0.52, 0.85, 6), 0, 0.45, 0);
      topY = 1.1;
      break;
    }
  }

  // Floating text billboard sprite
  const labelText = `${cat.toUpperCase()} ${Math.round((obj.confidence || 0.9) * 100)}%`;
  const sprite = createBillboardSprite(labelText, meta.hex);
  sprite.position.set(0, topY + 0.35, 0);
  sprite.visible = scene3dState.showLabels;
  sprite.name = "labelSprite";
  group.add(sprite);

  return group;
}

function highlightSelectedObject(objId) {
  clearSelectionHighlight();

  if (!objId || !scene3dState.objectsGroup || !scene3dState.scene) return;

  const targetGroup = scene3dState.objectsGroup.getObjectByName(objId);
  if (!targetGroup) return;

  scene3dState.selectedObjectId = objId;

  // Add emissive glow to child meshes
  targetGroup.traverse(child => {
    if (child.isMesh && child.material && child.material.emissive) {
      child.userData._origEmissive = child.material.emissive.getHex();
      child.material.emissive.setHex(0x004455);
    }
  });

  const box = new THREE.Box3().setFromObject(targetGroup);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  const hGroup = new THREE.Group();
  hGroup.name = "selectionHighlightGroup";

  // Glowing wireframe bounding box
  const boxGeo = new THREE.BoxGeometry(size.x + 0.35, size.y + 0.25, size.z + 0.35);
  const edges = new THREE.EdgesGeometry(boxGeo);
  const lineMat = new THREE.LineBasicMaterial({
    color: 0x00F0FF,
    linewidth: 2,
    transparent: true,
    opacity: 0.95,
  });
  const boxLine = new THREE.LineSegments(edges, lineMat);
  boxLine.position.copy(center);
  hGroup.add(boxLine);

  // Ground beacon ring
  const ringGeo = new THREE.RingGeometry(0.75, 0.95, 24);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    transparent: true,
    opacity: 0.85,
    side: THREE.DoubleSide,
  });
  const ringMesh = new THREE.Mesh(ringGeo, ringMat);
  ringMesh.rotation.x = -Math.PI / 2;
  ringMesh.position.set(center.x, 0.03, center.z);
  hGroup.add(ringMesh);

  scene3dState.scene.add(hGroup);
  scene3dState.selectionBracket = hGroup;
}

function clearSelectionHighlight() {
  if (scene3dState.selectedObjectId && scene3dState.objectsGroup) {
    const prevGroup = scene3dState.objectsGroup.getObjectByName(scene3dState.selectedObjectId);
    if (prevGroup) {
      prevGroup.traverse(child => {
        if (child.isMesh && child.material && child.material.emissive) {
          child.material.emissive.setHex(child.userData._origEmissive || 0x000000);
        }
      });
    }
  }
  if (scene3dState.selectionBracket && scene3dState.scene) {
    scene3dState.scene.remove(scene3dState.selectionBracket);
    scene3dState.selectionBracket = null;
  }
  scene3dState.selectedObjectId = null;
}

function frameCameraToScene(animate = true) {
  if (!scene3dState.camera || !scene3dState.controls || !scene3dState.objectsGroup) return;

  if (scene3dState.objectsGroup.children.length === 0) {
    scene3dState.camera.position.set(0, 14, 20);
    scene3dState.controls.target.set(0, 0, 0);
    scene3dState.controls.update();
    return;
  }

  const box = new THREE.Box3().setFromObject(scene3dState.objectsGroup);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  const maxDim = Math.max(size.x, size.y, size.z, 8);
  const fov = scene3dState.camera.fov * (Math.PI / 180);
  let cameraDistance = (maxDim / 2) / Math.tan(fov / 2);
  cameraDistance = Math.max(cameraDistance * 1.35, 12);

  const targetCamPos = new THREE.Vector3(
    center.x,
    center.y + (cameraDistance * 0.72),
    center.z + (cameraDistance * 0.95)
  );

  scene3dState.camera.position.copy(targetCamPos);
  scene3dState.controls.target.copy(center);
  scene3dState.controls.update();
}

function resizeThreeJsViewport() {
  if (!scene3dState.renderer || !scene3dState.camera || !dom.scene3dViewport) return;
  const width = dom.scene3dViewport.clientWidth;
  const height = dom.scene3dViewport.clientHeight;
  if (width === 0 || height === 0) return;
  scene3dState.camera.aspect = width / height;
  scene3dState.camera.updateProjectionMatrix();
  scene3dState.renderer.setSize(width, height);
}

function renderSceneLegend(catCounts) {
  if (!dom.scene3dLegend || !dom.scene3dLegendList) return;

  const categories = Object.keys(catCounts);
  if (categories.length === 0) {
    dom.scene3dLegend.style.display = "none";
    return;
  }

  dom.scene3dLegend.style.display = "block";
  let html = `<div class="legend-list">`;
  categories.sort().forEach(cat => {
    const meta = CATEGORY_MARKERS[cat] || { family: "generic", icon: "📦", hex: "#94A3B8" };
    const count = catCounts[cat];
    const isFiltered = dom.scene3dFilterCategory && dom.scene3dFilterCategory.value === cat;
    html += `
      <div class="legend-item ${isFiltered ? "active" : ""}" data-category="${cat}" title="Filter by ${cat.toUpperCase()}">
        <span class="legend-swatch" style="background-color: ${meta.hex}; color: ${meta.hex};"></span>
        <span class="legend-icon">${meta.icon}</span>
        <span class="legend-name">${cat.toUpperCase()}</span>
        <span class="legend-count">${count}</span>
      </div>
    `;
  });
  html += `</div>`;
  dom.scene3dLegendList.innerHTML = html;

  dom.scene3dLegendList.querySelectorAll(".legend-item").forEach(item => {
    item.addEventListener("click", () => {
      const clickedCat = item.getAttribute("data-category");
      if (dom.scene3dFilterCategory) {
        if (dom.scene3dFilterCategory.value === clickedCat) {
          dom.scene3dFilterCategory.value = "";
        } else {
          dom.scene3dFilterCategory.value = clickedCat;
        }
        renderSceneObjects(scene3dState.rawObjects);
      }
    });
  });
}

function initThreeJs() {
  if (scene3dState.isInitialized) return;
  if (typeof THREE === "undefined") {
    console.warn("Three.js not loaded.");
    return;
  }

  const container = dom.scene3dViewport;
  const canvas = dom.threejsCanvas;
  if (!container || !canvas) return;

  const width = container.clientWidth || 800;
  const height = container.clientHeight || 560;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x05080E);
  scene.fog = new THREE.FogExp2(0x05080E, 0.02);
  scene3dState.scene = scene;

  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 500);
  camera.position.set(0, 14, 20);
  scene3dState.camera = camera;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  scene3dState.renderer = renderer;

  if (typeof THREE.OrbitControls !== "undefined") {
    const controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.05;
    controls.minDistance = 2;
    controls.maxDistance = 90;
    scene3dState.controls = controls;
  }

  const ambLight = new THREE.AmbientLight(0xffffff, 0.65);
  scene.add(ambLight);

  const dirLight = new THREE.DirectionalLight(0x00F0FF, 0.85);
  dirLight.position.set(10, 20, 10);
  scene.add(dirLight);

  const dirLight2 = new THREE.DirectionalLight(0x3B82F6, 0.4);
  dirLight2.position.set(-10, 15, -10);
  scene.add(dirLight2);

  const grid = new THREE.GridHelper(30, 30, 0x00F0FF, 0x1E293B);
  grid.position.y = 0;
  scene.add(grid);
  scene3dState.gridHelper = grid;

  const objectsGroup = new THREE.Group();
  scene.add(objectsGroup);
  scene3dState.objectsGroup = objectsGroup;

  function animate() {
    requestAnimationFrame(animate);
    if (scene3dState.controls) scene3dState.controls.update();
    renderer.render(scene, camera);
  }
  animate();

  canvas.addEventListener("click", onSceneCanvasClick);

  // ResizeObserver for automatic viewport adjustment when AI Assistant sidebar toggles
  if (window.ResizeObserver && dom.scene3dViewport) {
    const ro = new ResizeObserver(() => {
      resizeThreeJsViewport();
    });
    ro.observe(dom.scene3dViewport);
  }

  scene3dState.isInitialized = true;
}

async function loadScene3d(caseId) {
  if (!caseId) return;

  dom.scene3dLoading.style.display = "flex";
  dom.scene3dEmptyState.style.display = "none";
  if (dom.scene3dLegend) dom.scene3dLegend.style.display = "none";

  const { ok, data } = await apiFetch(API.spatialVisualization(caseId));
  dom.scene3dLoading.style.display = "none";

  if (!ok) {
    dom.scene3dEmptyState.style.display = "flex";
    dom.scene3dEmptyText.textContent = "Failed to load 3D scene data.";
    return;
  }

  scene3dState.rawObjects = data.objects || [];
  populateSceneFilters(scene3dState.rawObjects);
  renderSceneObjects(scene3dState.rawObjects);
  frameCameraToScene(false);
}

function populateSceneFilters(objects) {
  const catSet = new Set();
  const evSet = new Set();
  objects.forEach(o => {
    const cat = (o.category || o.label || "").toLowerCase();
    const ev = o.source_evidence_filename || o.evidence_name || "";
    if (cat) catSet.add(cat);
    if (ev) evSet.add(ev);
  });

  dom.scene3dFilterCategory.innerHTML = `<option value="">All Categories</option>`;
  catSet.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c.toUpperCase();
    dom.scene3dFilterCategory.appendChild(opt);
  });

  dom.scene3dFilterEvidence.innerHTML = `<option value="">All Evidence</option>`;
  evSet.forEach(e => {
    const opt = document.createElement("option");
    opt.value = e;
    opt.textContent = e;
    dom.scene3dFilterEvidence.appendChild(opt);
  });
}

function renderSceneObjects(objects) {
  if (!scene3dState.objectsGroup) return;

  clearSelectionHighlight();
  if (dom.scene3dDetailsCard) {
    dom.scene3dDetailsCard.style.display = "none";
  }

  while (scene3dState.objectsGroup.children.length > 0) {
    scene3dState.objectsGroup.remove(scene3dState.objectsGroup.children[0]);
  }

  const filtered = (objects || []).filter(o => {
    const conf = o.confidence != null ? o.confidence : 1.0;
    if (conf < scene3dState.minConfidence) return false;
    const cat = dom.scene3dFilterCategory ? dom.scene3dFilterCategory.value : "";
    const objCat = (o.category || o.label || "").toLowerCase();
    if (cat && objCat !== cat) return false;
    const ev = dom.scene3dFilterEvidence ? dom.scene3dFilterEvidence.value : "";
    const objEv = o.source_evidence_filename || o.evidence_name || "";
    if (ev && objEv !== ev) return false;
    return true;
  });

  dom.scene3dCountBadge.textContent = `${filtered.length} object${filtered.length === 1 ? "" : "s"}`;

  if (filtered.length === 0) {
    dom.scene3dEmptyState.style.display = "flex";
    dom.scene3dEmptyText.textContent = "No localized objects match current confidence or category filter.";
    if (dom.scene3dLegend) dom.scene3dLegend.style.display = "none";
    return;
  }
  dom.scene3dEmptyState.style.display = "none";

  const catCounts = {};

  filtered.forEach(obj => {
    const cat = (obj.category || obj.label || "generic").toLowerCase();
    catCounts[cat] = (catCounts[cat] || 0) + 1;

    const meta = CATEGORY_MARKERS[cat] || { family: "generic", color: 0x94A3B8, hex: "#94A3B8" };
    let colHex = meta.color;
    if (obj.color_hex && obj.color_hex.startsWith("#")) {
      const parsed = parseInt(obj.color_hex.slice(1), 16);
      if (!isNaN(parsed)) colHex = parsed;
    }

    const pos = obj.position || (obj.spatial_coords ? [obj.spatial_coords.x, obj.spatial_coords.y, obj.spatial_coords.z] : [0, 0, 0]);

    const markerGroup = createProceduralMarker(obj, colHex);
    markerGroup.position.set(pos[0], pos[1], pos[2]);
    markerGroup.userData = obj;

    scene3dState.objectsGroup.add(markerGroup);
  });

  renderSceneLegend(catCounts);
}

function onSceneCanvasClick(e) {
  if (!scene3dState.camera || !scene3dState.objectsGroup) return;

  const rect = dom.threejsCanvas.getBoundingClientRect();
  const mouse = new THREE.Vector2();
  mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, scene3dState.camera);

  const intersects = raycaster.intersectObjects(scene3dState.objectsGroup.children, true);
  if (intersects.length > 0) {
    let hit = intersects[0].object;
    while (hit && !hit.userData?.object_id && hit.parent && hit.parent !== scene3dState.objectsGroup) {
      hit = hit.parent;
    }
    const data = hit?.userData;
    if (data && data.object_id) {
      show3dObjectDetails(data);
      return;
    }
  }

  // Clicked empty background
  clearSelectionHighlight();
  if (dom.scene3dDetailsCard) {
    dom.scene3dDetailsCard.style.display = "none";
  }
}

function show3dObjectDetails(obj) {
  highlightSelectedObject(obj.object_id);

  const cat = (obj.category || obj.label || "object").toLowerCase();
  const meta = CATEGORY_MARKERS[cat] || { family: "generic", icon: "📦", hex: "#94A3B8" };

  dom.detCardLabel.innerHTML = `<span style="display:inline-flex; align-items:center; gap:5px;"><span style="color:${meta.hex}; font-size:12px;">${meta.icon}</span> ${cat.toUpperCase()}</span>`;
  dom.detCardConf.textContent = `${Math.round((obj.confidence != null ? obj.confidence : 1.0) * 100)}%`;
  dom.detCardEvidence.textContent = obj.source_evidence_filename || obj.evidence_name || "—";

  if (obj.timestamp_seconds != null) {
    dom.detCardTimestampRow.style.display = "flex";
    dom.detCardTimestamp.textContent = `${parseFloat(obj.timestamp_seconds).toFixed(1)}s (Frame #${obj.frame_index ?? "—"})`;
  } else {
    dom.detCardTimestampRow.style.display = "none";
  }

  const bbox = obj.box_pixels || obj.box_normalized || [];
  dom.detCardBbox.textContent = Array.isArray(bbox) && bbox.length === 4
    ? `[${Math.round(bbox[0])}, ${Math.round(bbox[1])}, ${Math.round(bbox[2])}, ${Math.round(bbox[3])}]`
    : JSON.stringify(bbox);

  const pos = obj.position || (obj.spatial_coords ? [obj.spatial_coords.x, obj.spatial_coords.y, obj.spatial_coords.z] : [0, 0, 0]);
  dom.detCardPos.textContent = `(x:${pos[0].toFixed(2)}, y:${pos[1].toFixed(2)}, z:${pos[2].toFixed(2)})`;
  dom.scene3dDetailsCard.style.display = "block";

  dom.btnDetCardNavigate.onclick = () => {
    const targetEvId = obj.source_evidence_id || obj.evidence_id;
    if (targetEvId) {
      selectEvidence(targetEvId, true);
    }
  };
}

/* ══════════════════════════════════════════════════════════════════════════
   AI FORENSIC ASSISTANT
══════════════════════════════════════════════════════════════════════════ */
function enableChatAssistant() {
  dom.chatInput.disabled = false;
  dom.chatInput.placeholder = "Ask about this case's evidence…";
  dom.btnChatSend.disabled = false;
  dom.btnClearChat.disabled = false;
  dom.chatStatusBadge.textContent = "Ready";
  dom.chatStatusBadge.className = "badge badge-xs badge-emerald";
  dom.chatSuggestions.querySelectorAll(".chip-btn").forEach(b => b.disabled = false);
}

function disableChatAssistant() {
  dom.chatInput.disabled = true;
  dom.chatInput.placeholder = "Select an active case to begin…";
  dom.btnChatSend.disabled = true;
  dom.btnClearChat.disabled = true;
  dom.chatStatusBadge.textContent = "Standby";
  dom.chatStatusBadge.className = "badge badge-xs badge-slate";
  dom.chatSuggestions.querySelectorAll(".chip-btn").forEach(b => b.disabled = true);
  dom.chatMessages.innerHTML = `<p class="muted chat-hint" id="chat-empty-hint">Select an active case to ask questions about its evidence. All answers are strictly grounded in verified forensic data.</p>`;
}

async function loadChatHistory(caseId) {
  if (!caseId) return;
  enableChatAssistant();

  const { ok, data } = await apiFetch(API.chatHistory(caseId));
  if (!ok) return;

  dom.chatMessages.innerHTML = "";
  const msgs = data.messages || [];
  if (msgs.length === 0) {
    dom.chatMessages.innerHTML = `<p class="muted chat-hint" id="chat-empty-hint">No messages yet. Ask a question below or select a suggestion chip.</p>`;
  } else {
    msgs.forEach(m => renderChatMessage(m));
    dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
  }
}

function renderChatMessage(msg) {
  const isUser = msg.role === "user";
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${isUser ? "chat-bubble--user" : "chat-bubble--assistant"}`;
  const timeStr = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

  if (isUser) {
    bubble.innerHTML = `
      <div>${escapeHtml(msg.content)}</div>
      <div class="chat-bubble__meta"><span>Investigator</span><span>${timeStr}</span></div>
    `;
  } else {
    let contentHtml = escapeHtml(msg.content || "");
    // Replace citation pills [ev_xxx @ ts]
    contentHtml = contentHtml.replace(/\[(ev_[a-zA-Z0-9_\-]+)\s*@\s*([0-9\.]+)s?\]/g, (match, eid, ts) => {
      return `<a class="citation-pill" data-eid="${eid}" data-ts="${ts}">⏱️ ${eid} @ ${parseFloat(ts).toFixed(1)}s</a>`;
    });
    contentHtml = contentHtml.replace(/\[(ev_[a-zA-Z0-9_\-]+)\]/g, (match, eid) => {
      return `<a class="citation-pill" data-eid="${eid}">📁 ${eid}</a>`;
    });
    contentHtml = contentHtml.replace(/\n/g, "<br/>");

    bubble.innerHTML = `
      <div>${contentHtml}</div>
      <div class="chat-bubble__meta"><span>Forensic Assistant</span><span>${timeStr}</span></div>
    `;

    bubble.querySelectorAll(".citation-pill").forEach(pill => {
      pill.addEventListener("click", (e) => {
        e.preventDefault();
        const eid = pill.dataset.eid;
        if (eid) selectEvidence(eid, true);
      });
    });
  }

  dom.chatMessages.appendChild(bubble);
  dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
}

async function sendChatMessage(queryText = null) {
  const caseId = state.activeCaseId;
  if (!caseId) return;

  const query = (queryText || dom.chatInput.value || "").trim();
  if (!query) return;

  dom.chatInput.value = "";
  renderChatMessage({ role: "user", content: query, created_at: new Date().toISOString() });

  dom.chatInput.disabled = true;
  dom.btnChatSend.disabled = true;
  dom.chatSendText.style.display = "none";
  dom.chatSendSpinner.style.display = "inline-block";
  dom.chatStatusBadge.textContent = "Analyzing…";
  dom.chatStatusBadge.className = "badge badge-xs badge-amber";

  const { ok, data } = await apiFetch(API.chat(caseId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  dom.chatInput.disabled = false;
  dom.btnChatSend.disabled = false;
  dom.chatSendText.style.display = "inline";
  dom.chatSendSpinner.style.display = "none";
  dom.chatStatusBadge.textContent = "Ready";
  dom.chatStatusBadge.className = "badge badge-xs badge-emerald";

  if (ok) {
    const res = data.response || {};
    renderChatMessage({
      role: "assistant",
      content: res.answer || "No response generated.",
      created_at: data.created_at || new Date().toISOString(),
    });
  } else {
    let errorMsg = data.error || "Server error";
    if (errorMsg === "Failed to fetch") {
      errorMsg = "Unable to connect to the backend server. Please verify your connection and server status.";
    }
    renderChatMessage({
      role: "assistant",
      content: data.api_key_missing
        ? "⚠️ **Gemini API Key Required**\nPlease configure `GEMINI_API_KEY` in your `.env` file to enable conversational queries."
        : `❌ Query failed: ${errorMsg}`,
      created_at: new Date().toISOString(),
    });
  }
}

async function clearChatHistory() {
  const caseId = state.activeCaseId;
  if (!caseId) return;

  const { ok } = await apiFetch(API.chatHistory(caseId), { method: "DELETE" });
  if (ok) {
    dom.chatMessages.innerHTML = `<p class="muted chat-hint" id="chat-empty-hint">Chat history cleared. Ask a question below or pick a suggestion chip.</p>`;
    showToast("Chat history cleared.", "info");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   FORENSIC PDF DOWNLOAD
══════════════════════════════════════════════════════════════════════════ */
async function downloadForensicPdf() {
  const caseId = state.activeCaseId;
  if (!caseId) {
    showToast("Please select an active case container before generating report.", "warning");
    return;
  }

  dom.btnDownloadPdf.disabled = true;
  const originalText = dom.btnDownloadPdf.innerHTML;
  dom.btnDownloadPdf.innerHTML = `<span class="spin-loader"></span> Building Forensic Report…`;

  try {
    const { ok, data } = await apiFetch(API.reportPdf(caseId), {
      method: "POST",
      silent403: true,
    });

    if (ok && data && data.report && data.report.download_url) {
      showToast("Forensic PDF report generated successfully.", "success");
      // Trigger download
      const a = document.createElement("a");
      a.href = data.report.download_url;
      a.download = data.report.filename || `report_${caseId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } else {
      showToast(data.error || "Failed to generate PDF report.", "error");
    }
  } catch (err) {
    showToast(`Network error generating PDF: ${err.message}`, "error");
  } finally {
    dom.btnDownloadPdf.disabled = false;
    dom.btnDownloadPdf.innerHTML = originalText;
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   HEALTH & SYSTEM DIAGNOSTICS
══════════════════════════════════════════════════════════════════════════ */
function setHealthOnline(msg = "Core Engine: Online") {
  if (dom.healthStatusLabel) dom.healthStatusLabel.textContent = msg;
  if (dom.healthStatusPill) {
    dom.healthStatusPill.className = "health-pill";
    dom.healthStatusPill.title = "System services operational";
  }
}

function setHealthWarning(msg = "Core Engine: Warning") {
  if (dom.healthStatusLabel) dom.healthStatusLabel.textContent = msg;
  if (dom.healthStatusPill) {
    dom.healthStatusPill.className = "health-pill health-pill--warn";
    dom.healthStatusPill.title = "System services degraded";
  }
}

function setHealthDisconnected(msg = "Core Engine: Disconnected") {
  if (dom.healthStatusLabel) dom.healthStatusLabel.textContent = msg;
  if (dom.healthStatusPill) {
    dom.healthStatusPill.className = "health-pill health-pill--error";
    dom.healthStatusPill.title = "Backend server unreachable";
  }
}

let isHealthCheckInProgress = false;
let healthCheckTimer = null;

async function refreshHealth(silent = false) {
  if (isHealthCheckInProgress) return;
  isHealthCheckInProgress = true;
  try {
    const { ok, data } = await apiFetch(API.health);
    if (ok && data && (data.status === "ok" || data.status === "healthy")) {
      setHealthOnline("Core Engine: Online");
      if (dom.healthStatusPill && data.checks) {
        dom.healthStatusPill.title = Object.entries(data.checks).map(([k, v]) => `${k}: ${v}`).join("\n");
      }
      if (!silent) {
        showToast("System diagnostic verified: All storage and AI services online.", "info", 2000);
      }
    } else if (ok && data && data.status === "degraded") {
      if (dom.healthStatusPill && data.checks) {
        dom.healthStatusPill.title = Object.entries(data.checks).map(([k, v]) => `${k}: ${v}`).join("\n");
      }
      setHealthWarning("Core Engine: Degraded");
      if (!silent) {
        showToast("System diagnostic: Some services or storage degraded.", "warning");
      }
    } else {
      setHealthDisconnected("Core Engine: Disconnected");
      if (!silent) {
        showToast("System diagnostic: Backend unavailable.", "error");
      }
    }
  } catch (err) {
    setHealthDisconnected("Core Engine: Disconnected");
  } finally {
    isHealthCheckInProgress = false;
  }
}

function startHealthMonitor() {
  if (healthCheckTimer) clearInterval(healthCheckTimer);

  healthCheckTimer = setInterval(() => {
    // Suppress periodic health polling when tab is not visible
    if (document.visibilityState === "visible") {
      refreshHealth(true);
    }
  }, 30000);

  // Resume check immediately when window / tab regains visibility
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      refreshHealth(true);
    }
  });

  // Clean up timer on unload
  window.addEventListener("beforeunload", () => {
    if (healthCheckTimer) {
      clearInterval(healthCheckTimer);
      healthCheckTimer = null;
    }
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   WORKSPACE INITIALIZATION
══════════════════════════════════════════════════════════════════════════ */
async function initWorkspace() {
  // 1. Diagnostics & Active Health Monitoring
  await refreshHealth(true);
  startHealthMonitor();
  if (dom.btnRefreshHealth) {
    dom.btnRefreshHealth.addEventListener("click", () => refreshHealth(false));
  }

  // 2. Load Cases
  await loadCases();

  // 3. Setup Case Selector
  dom.caseSelect.addEventListener("change", () => {
    selectCase(dom.caseSelect.value);
  });

  // 4. Modal Event Listeners
  dom.btnOpenCreateModal.addEventListener("click", () => {
    dom.modalNewCase.style.display = "flex";
    dom.newCaseName.focus();
  });
  dom.btnCloseCaseModal.addEventListener("click", () => dom.modalNewCase.style.display = "none");
  dom.btnCancelCaseModal.addEventListener("click", () => dom.modalNewCase.style.display = "none");
  dom.btnCreateCase.addEventListener("click", createCase);

  // 5. Sidebar Navigation
  dom.navItems.forEach(item => {
    item.addEventListener("click", () => {
      switchView(item.dataset.view);
    });
  });

  // 6. Quick Jump buttons in Overview
  if (dom.btnQuickUpload) dom.btnQuickUpload.addEventListener("click", () => switchView("evidence"));
  if (dom.btnQuickFusion) dom.btnQuickFusion.addEventListener("click", () => switchView("fusion"));
  if (dom.btnViewAllEvidence) dom.btnViewAllEvidence.addEventListener("click", () => switchView("evidence"));

  // 7. Drag and Drop Ingestion
  initDragDrop();

  // 8. Modality Analysis Buttons
  if (dom.btnRunImageAnalysis) dom.btnRunImageAnalysis.addEventListener("click", runImageAnalysis);
  if (dom.btnRunAudioAnalysis) dom.btnRunAudioAnalysis.addEventListener("click", runAudioTranscription);
  if (dom.btnRunVideoAnalysis) dom.btnRunVideoAnalysis.addEventListener("click", runVideoAnalysis);
  if (dom.btnRunFusion) dom.btnRunFusion.addEventListener("click", runFusionAnalysis);
  if (dom.btnDownloadPdf) dom.btnDownloadPdf.addEventListener("click", downloadForensicPdf);

  // 8b. Direct Modality Evidence Selectors
  if (dom.selectImageEvidence) {
    dom.selectImageEvidence.addEventListener("change", (e) => {
      if (e.target.value) selectEvidence(e.target.value, false);
    });
  }
  if (dom.selectAudioEvidence) {
    dom.selectAudioEvidence.addEventListener("change", (e) => {
      if (e.target.value) selectEvidence(e.target.value, false);
    });
  }
  if (dom.selectVideoEvidence) {
    dom.selectVideoEvidence.addEventListener("change", (e) => {
      if (e.target.value) selectEvidence(e.target.value, false);
    });
  }

  // 9. AI Assistant Controls
  const notifyChatToggle = () => {
    if (!dom.wsChatPanel) return;
    const isCollapsed = dom.wsChatPanel.classList.contains("collapsed");
    document.body.classList.toggle("chat-panel-open", !isCollapsed);
    document.body.classList.toggle("chat-panel-collapsed", isCollapsed);
    setTimeout(() => {
      window.dispatchEvent(new Event("resize"));
      if (typeof resizeThreeJsViewport === "function") {
        resizeThreeJsViewport();
      }
      if (typeof updateVideoOverlay === "function") {
        updateVideoOverlay();
      }
    }, 260);
  };

  if (dom.btnToggleAssistant) {
    dom.btnToggleAssistant.addEventListener("click", () => {
      dom.wsChatPanel.classList.toggle("collapsed");
      notifyChatToggle();
    });
  }
  if (dom.btnCloseAssistant) {
    dom.btnCloseAssistant.addEventListener("click", () => {
      dom.wsChatPanel.classList.add("collapsed");
      notifyChatToggle();
    });
  }
  notifyChatToggle();
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
  if (dom.btnClearChat) dom.btnClearChat.addEventListener("click", clearChatHistory);
  if (dom.chatSuggestions) {
    dom.chatSuggestions.querySelectorAll(".chip-btn").forEach(btn => {
      btn.addEventListener("click", () => sendChatMessage(btn.dataset.query));
    });
  }

  // 10. 3D Scene Controls
  if (dom.btnScene3dResetCam) {
    dom.btnScene3dResetCam.addEventListener("click", () => {
      frameCameraToScene(true);
      showToast("Camera auto-framed to scene objects", "info");
    });
  }
  if (dom.btnScene3dRefresh) {
    dom.btnScene3dRefresh.addEventListener("click", () => {
      if (state.activeCaseId) loadScene3d(state.activeCaseId);
    });
  }
  if (dom.btnScene3dToggleGrid) {
    dom.btnScene3dToggleGrid.addEventListener("click", () => {
      scene3dState.showGrid = !scene3dState.showGrid;
      if (scene3dState.gridHelper) scene3dState.gridHelper.visible = scene3dState.showGrid;
      dom.btnScene3dToggleGrid.textContent = `Grid: ${scene3dState.showGrid ? "On" : "Off"}`;
    });
  }
  if (dom.btnScene3dToggleLabels) {
    dom.btnScene3dToggleLabels.addEventListener("click", () => {
      scene3dState.showLabels = !scene3dState.showLabels;
      dom.btnScene3dToggleLabels.textContent = `Labels: ${scene3dState.showLabels ? "On" : "Off"}`;
      if (scene3dState.objectsGroup) {
        scene3dState.objectsGroup.traverse(child => {
          if (child.name === "labelSprite") {
            child.visible = scene3dState.showLabels;
          }
        });
      }
    });
  }
  if (dom.scene3dFilterCategory) dom.scene3dFilterCategory.addEventListener("change", () => renderSceneObjects(scene3dState.rawObjects));
  if (dom.scene3dFilterEvidence) dom.scene3dFilterEvidence.addEventListener("change", () => renderSceneObjects(scene3dState.rawObjects));
  if (dom.scene3dConfSlider) {
    dom.scene3dConfSlider.addEventListener("input", (e) => {
      scene3dState.minConfidence = (parseFloat(e.target.value) || 30) / 100;
      if (dom.scene3dConfVal) dom.scene3dConfVal.textContent = `${e.target.value}%`;
      renderSceneObjects(scene3dState.rawObjects);
    });
  }
  if (dom.btnCloseDetCard) {
    dom.btnCloseDetCard.addEventListener("click", () => {
      clearSelectionHighlight();
      if (dom.scene3dDetailsCard) {
        dom.scene3dDetailsCard.style.display = "none";
      }
    });
  }

  // Responsive bounding box updates on image or window resize
  if (window.ResizeObserver && dom.evidenceImage) {
    const imgResizeObserver = new ResizeObserver(() => {
      if (state.currentImageAnalysis) {
        requestAnimationFrame(() => drawBoundingBoxes(state.currentImageAnalysis));
      }
    });
    imgResizeObserver.observe(dom.evidenceImage);
    if (dom.imageCanvasContainer) {
      imgResizeObserver.observe(dom.imageCanvasContainer);
    }
  }
  if (window.ResizeObserver && dom.evidenceVideo) {
    const vidResizeObserver = new ResizeObserver(() => {
      if (state.currentVideoAnalysis) {
        requestAnimationFrame(() => updateVideoOverlay());
      }
    });
    vidResizeObserver.observe(dom.evidenceVideo);
    if (dom.videoCanvasContainer) {
      vidResizeObserver.observe(dom.videoCanvasContainer);
    }
  }
  window.addEventListener("resize", () => {
    if (state.currentImageAnalysis) {
      requestAnimationFrame(() => drawBoundingBoxes(state.currentImageAnalysis));
    }
    if (state.currentVideoAnalysis) {
      requestAnimationFrame(() => updateVideoOverlay());
    }
    if (typeof resizeThreeJsViewport === "function") {
      resizeThreeJsViewport();
    }
  });

  // Video player playback synchronization events
  if (dom.evidenceVideo) {
    dom.evidenceVideo.addEventListener("timeupdate", () => updateVideoOverlay());
    dom.evidenceVideo.addEventListener("seeked", () => updateVideoOverlay());
    dom.evidenceVideo.addEventListener("loadedmetadata", () => updateVideoOverlay());
    dom.evidenceVideo.addEventListener("play", () => updateVideoOverlay());
    dom.evidenceVideo.addEventListener("pause", () => updateVideoOverlay());
  }

  // Fullscreen video toggle
  if (dom.btnVideoFullscreen && dom.videoStageBox) {
    dom.btnVideoFullscreen.addEventListener("click", () => {
      if (!document.fullscreenElement) {
        if (dom.videoStageBox.requestFullscreen) {
          dom.videoStageBox.requestFullscreen();
        } else if (dom.videoStageBox.webkitRequestFullscreen) {
          dom.videoStageBox.webkitRequestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen();
        }
      }
    });
  }

  // Responsive video bounding box updates on video container resize
  if (window.ResizeObserver && dom.evidenceVideo) {
    const vidResizeObserver = new ResizeObserver(() => {
      if (state.currentVideoAnalysis) {
        requestAnimationFrame(() => updateVideoOverlay());
      }
    });
    vidResizeObserver.observe(dom.evidenceVideo);
    if (dom.videoStageBox) {
      vidResizeObserver.observe(dom.videoStageBox);
    }
  }

  document.addEventListener("fullscreenchange", () => {
    if (state.currentVideoAnalysis) {
      setTimeout(() => updateVideoOverlay(), 80);
    }
  });
  document.addEventListener("webkitfullscreenchange", () => {
    if (state.currentVideoAnalysis) {
      setTimeout(() => updateVideoOverlay(), 80);
    }
  });

  // Responsive image bounding box updates on image container resize
  if (window.ResizeObserver && (dom.evidenceImage || dom.imageStageBox)) {
    const imgResizeObserver = new ResizeObserver(() => {
      if (state.currentImageAnalysis) {
        requestAnimationFrame(() => drawBoundingBoxes(state.currentImageAnalysis));
      }
    });
    if (dom.evidenceImage) imgResizeObserver.observe(dom.evidenceImage);
    if (dom.imageStageBox) imgResizeObserver.observe(dom.imageStageBox);
  }

  // Image Analysis Subtabs & Inline Chat
  initImageSubtabs();
  initImageChat();

  // Audio Analysis Subtabs, Multilingual & Q&A Controls
  initAudioSubtabs();
  initAudioIntelligenceControls();

  // Video Analysis Subtabs
  initVideoSubtabs();

  // 11. Initial View
  switchView("overview");

  // Wire Logout Button
  const btnLogout = document.getElementById("btn-logout");
  if (btnLogout) {
    btnLogout.addEventListener("click", async () => {
      try {
        await apiFetch("/api/auth/logout", { method: "POST" });
      } finally {
        window.location.href = "/login";
      }
    });
  }

  // Select first case if available
  if (state.cases.length > 0) {
    dom.caseSelect.value = state.cases[0].case_id;
    await selectCase(state.cases[0].case_id);
  }
}

document.addEventListener("DOMContentLoaded", initWorkspace);
