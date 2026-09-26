/**
 * Main Application Controller for Cybercrime Predictive Analytics Dashboard.
 * Coordinates Geospatial Map, Chart Analytics, Prediction Workbench, Tabs, and Modal Audit.
 */

import { API } from "./api.js";
import { MapController } from "./map.js";
import { ChartController } from "./charts.js";

// Preset Demo Scenarios
const PRESETS = {
  urgent_investment: {
    crime_category: "INVESTMENT_FRAUD",
    reported_amount: 85000,
    payment_channel: "UPI",
    mule_bank_code: "BANK_SBI_SYNTH",
    mule_account_tier: "NEW_DIGITAL",
    mule_branch_zone: "ZONE_WEST",
    reporting_delay_mins: 25,
    incident_hour: 15,
    incident_day_of_week: 4,
  },
  upi_phishing: {
    crime_category: "PHISHING_UPI",
    reported_amount: 42000,
    payment_channel: "UPI",
    mule_bank_code: "BANK_HDFC_SYNTH",
    mule_account_tier: "NEW_DIGITAL",
    mule_branch_zone: "ZONE_NORTH",
    reporting_delay_mins: 18,
    incident_hour: 18,
    incident_day_of_week: 5,
  },
  delayed_loan: {
    crime_category: "LOAN_SCAM",
    reported_amount: 18000,
    payment_channel: "NEFT",
    mule_bank_code: "BANK_PNB_SYNTH",
    mule_account_tier: "RURAL_REGIONAL",
    mule_branch_zone: "ZONE_SOUTH",
    reporting_delay_mins: 190,
    incident_hour: 11,
    incident_day_of_week: 2,
  },
};

document.addEventListener("DOMContentLoaded", async () => {
  console.log("Initializing Cybercrime Predictive Analytics Dashboard...");

  // 1. Initialize Geospatial Map
  MapController.init("map");

  // 2. Setup Navigation, Tabs, Filters & Listeners
  setupTabListeners();
  setupZoneFilterListeners();
  setupFormListeners();
  setupModalListeners();

  // 3. Load Core Telemetry & Data
  await loadDashboardData();
});

/**
 * Fetch and populate core dashboard telemetry.
 */
async function loadDashboardData() {
  try {
    const [stats, atms, predictions, modelInfo] = await Promise.all([
      API.getStats(),
      API.getATMs(),
      API.getPredictions(10),
      API.getModelInfo(),
    ]);

    // Update Overview Counters
    const kpiComplaints = document.getElementById("kpiTotalComplaints");
    const kpiCashouts = document.getElementById("kpiCashouts");
    const kpiATMs = document.getElementById("kpiActiveATMs");
    const kpiAlerts = document.getElementById("kpiAlerts");

    if (kpiComplaints) kpiComplaints.innerText = (stats.total_complaints || 0).toLocaleString();
    if (kpiCashouts) kpiCashouts.innerText = (stats.total_cashouts || 0).toLocaleString();
    if (kpiATMs) kpiATMs.innerText = (stats.active_atms || 0).toLocaleString();
    if (kpiAlerts) kpiAlerts.innerText = (stats.total_predictions || 0).toLocaleString();

    // Render Tactical ATM Markers
    MapController.renderATMs(atms);

    // Render Analytics Charts
    ChartController.renderCharts(stats);

    // Populate Recent Dispatch Log
    renderAlertHistory(predictions);

    // Cache model info for audit modal
    window.modelInfoData = modelInfo;
  } catch (err) {
    showToast("Failed to load initial dashboard telemetry: " + err.message, "error");
  }
}

/**
 * Configure tabs in secondary lower analytics panel.
 */
function setupTabListeners() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTabId = btn.getAttribute("data-tab");

      // Update button active state
      tabButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      // Update pane active state
      tabPanes.forEach(pane => {
        if (pane.id === targetTabId) {
          pane.classList.add("active");
        } else {
          pane.classList.remove("active");
        }
      });

      // Trigger window resize so Chart.js recalculates dimensions if switched
      if (targetTabId === "tab-analytics") {
        window.dispatchEvent(new Event("resize"));
      }
    });
  });
}

/**
 * Configure zone filter buttons above tactical map.
 */
function setupZoneFilterListeners() {
  const zoneButtons = document.querySelectorAll(".btn-zone-filter");

  zoneButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      zoneButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const zoneId = btn.getAttribute("data-zone");
      MapController.filterByZone(zoneId);
    });
  });
}

/**
 * Setup prediction intake form, presets, and submission handling.
 */
function setupFormListeners() {
  const form = document.getElementById("predictionForm");
  const submitBtn = document.getElementById("btnPredict");

  // Preset Buttons
  document.querySelectorAll("[data-preset]").forEach(btn => {
    btn.addEventListener("click", () => {
      // Toggle active style
      document.querySelectorAll("[data-preset]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const presetKey = btn.getAttribute("data-preset");
      const data = PRESETS[presetKey];
      if (data) {
        Object.entries(data).forEach(([key, val]) => {
          const field = form.elements[key];
          if (field) field.value = val;
        });
      }
    });
  });

  // Form Submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Forecasting Target Location...</span>`;

    const formData = new FormData(form);
    const payload = {
      crime_category: formData.get("crime_category"),
      reported_amount: parseFloat(formData.get("reported_amount")),
      payment_channel: formData.get("payment_channel"),
      mule_bank_code: formData.get("mule_bank_code"),
      mule_account_tier: formData.get("mule_account_tier"),
      mule_branch_zone: formData.get("mule_branch_zone"),
      reporting_delay_mins: parseFloat(formData.get("reporting_delay_mins")),
      incident_hour: parseInt(formData.get("incident_hour"), 10),
      incident_day_of_week: parseInt(formData.get("incident_day_of_week"), 10),
      complaint_timestamp: new Date().toISOString().replace("T", " ").substring(0, 19),
    };

    try {
      const result = await API.predict(payload);
      renderPredictionResult(result);
      MapController.highlightPrediction(result.predicted_atm_id, result.top_candidates);

      // Refresh recent alert history and counters
      const updatedPredictions = await API.getPredictions(10);
      renderAlertHistory(updatedPredictions);

      const kpiAlerts = document.getElementById("kpiAlerts");
      if (kpiAlerts) {
        const currentAlerts = parseInt(kpiAlerts.innerText.replace(/,/g, "") || "0", 10);
        kpiAlerts.innerText = (currentAlerts + 1).toLocaleString();
      }

      showToast(`Forecast Generated: Target ${result.predicted_atm_id} (Priority: ${result.priority_level} · Score: ${result.priority_score}/100)`, "success");
    } catch (err) {
      showToast("Prediction request failed: " + err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>Generate Predictive Forecast</span>`;
    }
  });
}

/**
 * Escape HTML to prevent injection in dynamic elements.
 */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Render predictive inference results to the output card.
 */
function renderPredictionResult(result) {
  const card = document.getElementById("forecastCard");
  if (!card) return;
  card.style.display = "block";

  // Target ATM ID & Zone
  const atmEl = document.getElementById("predAtmId");
  const zoneEl = document.getElementById("predZoneId");
  const confEl = document.getElementById("predConfidence");
  const riskBadge = document.getElementById("predRiskBadge");
  const windowEl = document.getElementById("predWindow");

  if (atmEl) atmEl.innerText = result.predicted_atm_id;
  if (zoneEl) zoneEl.innerText = `(${result.predicted_zone_id.replace("ZONE_", "Zone ")})`;
  if (confEl) confEl.innerText = `${(result.confidence_score * 100).toFixed(1)}%`;

  // Risk Badge
  if (riskBadge) {
    const level = (result.risk_level || "LOW").toLowerCase();
    riskBadge.className = `risk-tag risk-${level}`;
    riskBadge.innerText = `${result.risk_level} RISK`;
  }

  // Milestone 1 Feature 6: Operational Intervention Priority Score
  const priorityScoreEl = document.getElementById("predPriorityScore");
  const priorityBadge = document.getElementById("predPriorityBadge");
  const priorityProgress = document.getElementById("predPriorityProgress");
  const priorityReasonsEl = document.getElementById("predPriorityReasons");

  const score = typeof result.priority_score === "number" ? result.priority_score : 0;
  const pLevel = (result.priority_level || "LOW").toUpperCase();

  if (priorityScoreEl) {
    priorityScoreEl.innerText = score;
  }

  if (priorityBadge) {
    priorityBadge.className = `priority-tag priority-${pLevel.toLowerCase()}`;
    priorityBadge.innerText = `${pLevel}`;
  }

  if (priorityProgress) {
    priorityProgress.style.width = `${Math.min(100, Math.max(0, score))}%`;
    if (pLevel === "CRITICAL") {
      priorityProgress.style.backgroundColor = "var(--risk-critical)";
      if (priorityScoreEl) priorityScoreEl.style.color = "var(--risk-critical)";
    } else if (pLevel === "HIGH") {
      priorityProgress.style.backgroundColor = "var(--risk-high)";
      if (priorityScoreEl) priorityScoreEl.style.color = "var(--risk-high)";
    } else if (pLevel === "MEDIUM") {
      priorityProgress.style.backgroundColor = "var(--risk-moderate)";
      if (priorityScoreEl) priorityScoreEl.style.color = "var(--risk-moderate)";
    } else {
      priorityProgress.style.backgroundColor = "var(--risk-low)";
      if (priorityScoreEl) priorityScoreEl.style.color = "var(--risk-low)";
    }
  }

  if (priorityReasonsEl && Array.isArray(result.priority_reasons)) {
    priorityReasonsEl.innerHTML = result.priority_reasons
      .map(r => `
        <div class="priority-reason-item">
          <span class="priority-reason-bullet">&#8226;</span>
          <span>${escapeHtml(r)}</span>
        </div>
      `)
      .join("");
  }

  // Intervention Window (HH:MM – HH:MM)
  if (windowEl && result.predicted_window_start && result.predicted_window_end) {
    const startTime = result.predicted_window_start.substring(11, 16);
    const endTime = result.predicted_window_end.substring(11, 16);
    windowEl.innerText = `${startTime} – ${endTime} hrs`;
  }

  // Milestone 1 Feature 7: Tactical Investigator Action Playbook
  const playbookCard = document.getElementById("playbookCard");
  const playbookBadge = document.getElementById("playbookDispositionBadge");
  const playbookSummary = document.getElementById("playbookSummary");
  const playbookList = document.getElementById("playbookActionsList");
  const copyBtn = document.getElementById("btnCopyDispatch");

  if (result.playbook) {
    if (playbookCard) playbookCard.style.display = "block";
    if (playbookBadge) playbookBadge.innerText = (result.playbook.disposition || "TACTICAL SOP").replace(/_/g, " ");
    if (playbookSummary) playbookSummary.innerText = result.playbook.summary || "";

    if (playbookList && Array.isArray(result.playbook.actions)) {
      playbookList.innerHTML = result.playbook.actions
        .map(action => {
          const urgencyClass = (action.urgency || "standard").toLowerCase();
          return `
            <div class="playbook-action-card" id="action-step-${action.step}">
              <div class="playbook-card-header">
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span class="playbook-step-badge urgency-${urgencyClass}">Step ${action.step} · ${action.urgency}</span>
                  <span class="playbook-action-title">${escapeHtml(action.title)}</span>
                </div>
                <span class="playbook-action-target">${escapeHtml(action.target)}</span>
              </div>
              <div class="playbook-action-desc">${escapeHtml(action.description)}</div>
              <div class="playbook-action-rationale">&#8627; Rationale: ${escapeHtml(action.rationale)}</div>
              <div class="playbook-action-footer">
                <label class="playbook-checkbox-label">
                  <input type="checkbox" onchange="this.closest('.playbook-action-card').classList.toggle('completed', this.checked)">
                  <span>Mark Executed</span>
                </label>
              </div>
            </div>
          `;
        })
        .join("");
    }

    if (copyBtn) {
      copyBtn.onclick = async () => {
        const textToCopy = result.playbook.dispatch_brief || result.playbook.summary || "";
        try {
          await navigator.clipboard.writeText(textToCopy);
          const icon = document.getElementById("copyBriefIcon");
          const text = document.getElementById("copyBriefText");
          if (icon) icon.innerText = "✓";
          if (text) text.innerText = "Copied to Clipboard!";
          copyBtn.classList.add("copied");
          showToast("Tactical Dispatch Brief copied to clipboard!", "success");
          setTimeout(() => {
            if (icon) icon.innerHTML = "&#128203;";
            if (text) text.innerText = "Copy Dispatch Brief";
            copyBtn.classList.remove("copied");
          }, 2500);
        } catch (e) {
          showToast("Failed to copy brief: " + e.message, "error");
        }
      };
    }
  } else if (playbookCard) {
    playbookCard.style.display = "none";
  }

  // Explainability Reason Codes (Pills inside accordion)
  const reasonsContainer = document.getElementById("predReasons");
  if (reasonsContainer && result.explanation_codes) {
    reasonsContainer.innerHTML = result.explanation_codes
      .map(code => `<span class="reason-pill">${formatReason(code)}</span>`)
      .join("");
  }

  // Top 5 Ranked Candidates
  const tbody = document.getElementById("candidateTableBody");
  if (tbody && result.top_candidates) {
    tbody.innerHTML = result.top_candidates
      .map(c => `
        <tr>
          <td><b>#${c.rank}</b></td>
          <td><span style="color: var(--accent-blue); font-weight: 700;">${c.atm_id}</span></td>
          <td>${c.bank_code.replace("BANK_", "").replace("_SYNTH", "")}</td>
          <td>${c.zone_id.replace("ZONE_", "")}</td>
          <td><b>${(c.probability * 100).toFixed(1)}%</b></td>
          <td>
            <div class="prob-track">
              <div class="prob-fill" style="width: ${Math.min(100, Math.round(c.probability * 300))}%;"></div>
            </div>
          </td>
        </tr>
      `)
      .join("");
  }

  // Smooth scroll into view on smaller displays
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/**
 * Render recent prediction alerts to the dispatch audit log.
 */
function renderAlertHistory(predictions) {
  const container = document.getElementById("alertHistoryBody");
  if (!container) return;

  if (!predictions || predictions.length === 0) {
    container.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 12px;">No recent alerts generated.</td></tr>`;
    return;
  }

  container.innerHTML = predictions
    .map(p => {
      const pLevel = (p.priority_level || p.risk_level || "LOW").toUpperCase();
      const pScore = typeof p.priority_score === "number" ? p.priority_score : null;
      return `
      <tr>
        <td><small style="color: var(--text-muted); font-family: monospace;">${p.prediction_timestamp.substring(11, 19)}</small></td>
        <td><b style="color: var(--accent-blue);">${p.predicted_atm_id}</b></td>
        <td>${p.predicted_zone_id.replace("ZONE_", "")}</td>
        <td>
          <span class="priority-tag priority-${pLevel.toLowerCase()}">
            ${pScore !== null ? `${pScore} · ` : ""}${pLevel}
          </span>
        </td>
        <td><span style="font-size: 0.72rem; color: var(--risk-low); font-weight: 700; letter-spacing: 0.04em;">DISPATCH READY</span></td>
      </tr>
    `;
    })
    .join("");
}

/**
 * Map explanation codes to human-readable intelligence descriptors.
 */
function formatReason(code) {
  const map = {
    ON_US_BANK_MATCH: "Same Bank Network ('On-Us')",
    HIGH_VELOCITY_CHANNEL: "High Velocity Rail (Fast Transit)",
    HOTSPOT_CORRIDOR: "Historical Hotspot (Point-in-Time)",
    HIGH_CAPACITY_TARGET: "High Cash Dispenser Fit",
    LOW_SURVEILLANCE_RISK: "Standalone Kiosk Setting",
    GEOGRAPHIC_PROXIMITY: "Branch Corridor Proximity",
    ZONE_AFFINITY_MATCH: "Zone Affinity Corroboration",
  };
  return map[code] || code;
}

/**
 * Modal dialog listeners for Model Provenance & Evaluation Audit.
 */
function setupModalListeners() {
  const modal = document.getElementById("modelModal");
  const openBtn = document.getElementById("btnModelInfo");
  const closeBtn = document.getElementById("closeModalBtn");

  if (!modal || !openBtn || !closeBtn) return;

  openBtn.addEventListener("click", () => {
    const info = window.modelInfoData;
    if (info && info.p3_eval_metrics) {
      const m = info.p3_eval_metrics;
      const modelNameEl = document.getElementById("modalModelName");
      const top1El = document.getElementById("modalTop1");
      const top3El = document.getElementById("modalTop3");
      const top5El = document.getElementById("modalTop5");
      const zoneEl = document.getElementById("modalZone");
      const temporalEl = document.getElementById("modalTemporal");
      const brierEl = document.getElementById("modalBrier");
      const logLossEl = document.getElementById("modalLogLoss");
      const samplesEl = document.getElementById("modalSamples");

      if (modelNameEl) modelNameEl.innerText = info.model_name;
      if (top1El) top1El.innerText = `${m.top1_spatial_accuracy_pct}% (Baseline: ${m.random_baseline_top1_pct}%)`;
      if (top3El) top3El.innerText = `${m.top3_spatial_accuracy_pct}%`;
      if (top5El) top5El.innerText = `${m.top5_spatial_accuracy_pct}%`;
      if (zoneEl) zoneEl.innerText = `${m.zone_level_accuracy_pct}%`;
      if (temporalEl) temporalEl.innerText = `${m.temporal_window_coverage_pct}% (Empirical IQR 25th–75th)`;
      if (brierEl) brierEl.innerText = `${m.calibrated_brier_score}`;
      if (logLossEl) logLossEl.innerText = `${m.calibrated_log_loss}`;
      if (samplesEl && info.chronological_boundaries) {
        samplesEl.innerText = `${m.n_test_samples} complaints (${info.chronological_boundaries.p3_start} to ${info.chronological_boundaries.p3_end})`;
      }
    }
    modal.style.display = "flex";
  });

  const closeModal = () => {
    modal.style.display = "none";
  };

  closeBtn.addEventListener("click", closeModal);

  window.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.style.display === "flex") {
      closeModal();
    }
  });
}

/**
 * Toast notifications for user feedback.
 */
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.innerText = message;
  toast.style.position = "fixed";
  toast.style.bottom = "20px";
  toast.style.right = "20px";
  toast.style.padding = "9px 16px";
  toast.style.borderRadius = "6px";
  toast.style.background = type === "error" ? "#ef4444" : (type === "success" ? "#0284c7" : "#1e293b");
  toast.style.border = "1px solid rgba(255,255,255,0.15)";
  toast.style.color = "#ffffff";
  toast.style.fontSize = "12px";
  toast.style.fontWeight = "600";
  toast.style.zIndex = "9999";
  toast.style.boxShadow = "0 4px 14px rgba(0,0,0,0.5)";
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease-out";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}
