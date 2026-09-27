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
  setupClusterListeners();
  setupConvergenceListeners();

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

    // Load Emerging Cash-Out Clusters
    await loadClusters();

    // Load Repeated Spatial Convergences (Feature 2)
    await loadConvergences();

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
 * Setup prediction intake form, presets, validation, and submission handling.
 */
function setupFormListeners() {
  const form = document.getElementById("predictionForm");
  const submitBtn = document.getElementById("btnPredict");
  let isPredicting = false;

  function clearFormErrors() {
    const generalErr = document.getElementById("formGeneralError");
    if (generalErr) {
      generalErr.style.display = "none";
      const msgEl = generalErr.querySelector(".error-msg");
      if (msgEl) msgEl.innerText = "";
    }
    document.querySelectorAll(".field-error").forEach(el => {
      el.innerText = "";
      el.classList.remove("active");
    });
    document.querySelectorAll(".input-invalid").forEach(el => {
      el.classList.remove("input-invalid");
    });
  }

  function setFieldError(fieldName, message) {
    const errEl = document.getElementById(`err_${fieldName}`);
    const inputEl = document.getElementById(fieldName);
    if (errEl) {
      errEl.innerText = message;
      errEl.classList.add("active");
    }
    if (inputEl) {
      inputEl.classList.add("input-invalid");
    }
  }

  function setGeneralError(message) {
    const generalErr = document.getElementById("formGeneralError");
    if (generalErr) {
      const msgEl = generalErr.querySelector(".error-msg");
      if (msgEl) msgEl.innerText = message;
      generalErr.style.display = "flex";
    }
  }

  // Real-time error clearing when user edits any control
  form.querySelectorAll("input, select").forEach(control => {
    const clearCurrent = () => {
      control.classList.remove("input-invalid");
      const errEl = document.getElementById(`err_${control.id}`);
      if (errEl) {
        errEl.innerText = "";
        errEl.classList.remove("active");
      }
      const remaining = form.querySelectorAll(".input-invalid");
      if (remaining.length === 0) {
        const generalErr = document.getElementById("formGeneralError");
        if (generalErr) generalErr.style.display = "none";
      }
    };
    control.addEventListener("input", clearCurrent);
    control.addEventListener("change", clearCurrent);
  });

  // Preset Buttons
  document.querySelectorAll("[data-preset]").forEach(btn => {
    btn.addEventListener("click", () => {
      clearFormErrors();

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
    if (isPredicting) return; // Prevent duplicate concurrent submissions

    clearFormErrors();

    // Client-side pre-validation
    let hasClientErrors = false;
    const rawAmount = form.elements["reported_amount"].value.trim();
    const rawDelay = form.elements["reporting_delay_mins"].value.trim();
    const rawHour = form.elements["incident_hour"].value.trim();
    const rawDay = form.elements["incident_day_of_week"].value;

    const amount = parseFloat(rawAmount);
    if (!rawAmount || isNaN(amount) || amount <= 0) {
      setFieldError("reported_amount", "Reported loss amount must be greater than ₹0.");
      hasClientErrors = true;
    }

    const delay = parseFloat(rawDelay);
    if (!rawDelay || isNaN(delay) || delay < 0) {
      setFieldError("reporting_delay_mins", "Reporting delay must be 0 minutes or greater.");
      hasClientErrors = true;
    }

    const hour = parseInt(rawHour, 10);
    if (!rawHour || isNaN(hour) || hour < 0 || hour > 23) {
      setFieldError("incident_hour", "Incident hour must be an integer between 0 and 23.");
      hasClientErrors = true;
    }

    const day = parseInt(rawDay, 10);
    if (isNaN(day) || day < 0 || day > 6) {
      setFieldError("incident_day_of_week", "Incident day of week must be between 0 (Mon) and 6 (Sun).");
      hasClientErrors = true;
    }

    const categoricalFields = [
      ["crime_category", "Crime category is required."],
      ["payment_channel", "Payment rail is required."],
      ["mule_bank_code", "Beneficiary mule bank is required."],
      ["mule_branch_zone", "Mule branch zone is required."],
      ["mule_account_tier", "Account classification is required."],
    ];

    categoricalFields.forEach(([fId, msg]) => {
      if (!form.elements[fId] || !form.elements[fId].value) {
        setFieldError(fId, msg);
        hasClientErrors = true;
      }
    });

    if (hasClientErrors) {
      setGeneralError("Please correct the invalid fields highlighted below before submitting.");
      return;
    }

    isPredicting = true;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Forecasting Target Location...</span>`;

    const payload = {
      crime_category: form.elements["crime_category"].value,
      reported_amount: amount,
      payment_channel: form.elements["payment_channel"].value,
      mule_bank_code: form.elements["mule_bank_code"].value,
      mule_account_tier: form.elements["mule_account_tier"].value,
      mule_branch_zone: form.elements["mule_branch_zone"].value,
      reporting_delay_mins: delay,
      incident_hour: hour,
      incident_day_of_week: day,
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

      // Refresh clusters & spatial convergences
      loadClusters();
      loadConvergences();

      showToast(`Forecast Generated: Target ${result.predicted_atm_id} (Priority: ${result.priority_level} · Score: ${result.priority_score}/100)`, "success");
    } catch (err) {
      if (err.fieldErrors && Object.keys(err.fieldErrors).length > 0) {
        Object.entries(err.fieldErrors).forEach(([field, msg]) => {
          setFieldError(field, msg);
        });
        setGeneralError(err.message || "Validation failed on submitted fields. Please check the marked inputs.");
      } else {
        setGeneralError(err.message || "An unexpected error occurred while processing the forecast.");
      }
      showToast(err.message || "Prediction request failed.", "error");
    } finally {
      isPredicting = false;
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>Run Predictive Forecast</span>`;
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

  // Dynamic card border accent based on priority
  if (pLevel === "CRITICAL") {
    card.style.borderTopColor = "var(--risk-critical)";
  } else if (pLevel === "HIGH") {
    card.style.borderTopColor = "var(--risk-high)";
  } else if (pLevel === "MEDIUM") {
    card.style.borderTopColor = "var(--risk-moderate)";
  } else {
    card.style.borderTopColor = "var(--risk-low)";
  }

  // Hero Immediate Action Directive
  const heroActionEl = document.getElementById("heroActionDirective");
  if (heroActionEl) {
    if (result.playbook && result.playbook.summary) {
      heroActionEl.innerText = result.playbook.summary;
    } else if (result.playbook && Array.isArray(result.playbook.actions) && result.playbook.actions.length > 0) {
      heroActionEl.innerText = `${result.playbook.actions[0].title}: ${result.playbook.actions[0].description}`;
    } else {
      heroActionEl.innerText = `Dispatch nearest patrol to secure ${result.predicted_atm_id} in ${result.predicted_zone_id.replace("ZONE_", "Zone ")}; verify CCTV feeds and monitor cash-out corridor.`;
    }
  }

  // Facility Type & Bank Network
  const typeSummaryEl = document.getElementById("predAtmTypeSummary");
  const bankSummaryEl = document.getElementById("predAtmBankSummary");
  const isKiosk = Array.isArray(result.explanation_codes) && result.explanation_codes.includes("LOW_SURVEILLANCE_RISK");
  if (typeSummaryEl) {
    typeSummaryEl.innerText = isKiosk ? "Standalone Kiosk" : "Branch-Attached ATM";
  }
  if (bankSummaryEl) {
    const topMatch = result.top_candidates && result.top_candidates[0];
    const bName = topMatch && topMatch.bank_code ? topMatch.bank_code.replace("BANK_", "").replace("_SYNTH", "") : "ATM Network";
    bankSummaryEl.innerText = `${bName} (${result.predicted_zone_id.replace("ZONE_", "Zone ")})`;
  }

  // Focus on Map button
  const focusBtn = document.getElementById("btnFocusTargetMap");
  if (focusBtn) {
    focusBtn.onclick = () => {
      MapController.centerATM(result.predicted_atm_id);
    };
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
 * Configure cluster analysis toolbar listeners (Feature 1).
 */
function setupClusterListeners() {
  const winSelect = document.getElementById("clusterWindowSelect");
  const srcSelect = document.getElementById("clusterSourceSelect");
  const refreshBtn = document.getElementById("btnRefreshClusters");

  if (winSelect) winSelect.addEventListener("change", () => loadClusters());
  if (srcSelect) srcSelect.addEventListener("change", () => loadClusters());
  if (refreshBtn) refreshBtn.addEventListener("click", () => loadClusters());
}

/**
 * Fetch and refresh emerging cash-out clusters from backend API.
 */
async function loadClusters() {
  const winSelect = document.getElementById("clusterWindowSelect");
  const srcSelect = document.getElementById("clusterSourceSelect");
  const windowHours = winSelect ? parseInt(winSelect.value, 10) : 24;
  const source = srcSelect ? srcSelect.value : "all";

  const summaryEl = document.getElementById("clusterStatusSummary");
  if (summaryEl) summaryEl.innerText = `Analyzing rolling ${windowHours}h window for emerging concentrations...`;

  try {
    const data = await API.getClusters({ window_hours: windowHours, min_events: 2, source: source });
    renderClusters(data);
  } catch (err) {
    if (summaryEl) summaryEl.innerText = `Cluster detection error: ${err.message}`;
  }
}

/**
 * Render emerging cash-out clusters to table and update badge count.
 */
function renderClusters(data) {
  const badge = document.getElementById("clusterBadgeCount");
  const summaryEl = document.getElementById("clusterStatusSummary");
  const tbody = document.getElementById("clusterTableBody");
  if (!tbody) return;

  const total = data.total_clusters_detected || (data.clusters ? data.clusters.length : 0);
  if (badge) badge.innerText = total;

  if (summaryEl) {
    summaryEl.innerText = `Detected ${total} emerging cluster${total === 1 ? "" : "s"} across rolling ${data.rolling_window_hours || data.window_hours || 24}h temporal window (${data.window_start || ""} to ${data.window_end || ""}).`;
  }

  if (!data.clusters || data.clusters.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 16px;">No emerging cash-out clusters detected in the selected time window.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.clusters
    .map(c => {
      const isAlert = c.cluster_type === "PREDICTED_CONVERGENCE";
      const typeLabel = isAlert ? "Alert Convergence" : "Cash-Out Surge";
      const typeClass = isAlert ? "cluster-type-alert" : "cluster-type-cashout";
      const sevClass = `priority-${(c.severity_level || "low").toLowerCase()}`;
      const atmsList = c.involved_atm_ids && c.involved_atm_ids.length > 0 ? c.involved_atm_ids.join(", ") : c.primary_atm_id;

      return `
      <tr>
        <td><span class="cluster-id-badge">${c.cluster_id}</span></td>
        <td><span class="cluster-type-tag ${typeClass}">${typeLabel}</span></td>
        <td><span class="priority-tag ${sevClass}">${c.severity_level}</span></td>
        <td><span class="cluster-score-pill">${c.emergence_score}/100</span></td>
        <td><b>${c.primary_atm_id}</b> <small style="color: var(--text-muted);">(${c.zone.replace("ZONE_", "")})</small></td>
        <td><small style="color: #cbd5e1; font-family: monospace;">${atmsList}</small></td>
        <td>
          <b>${c.complaint_count || c.complaint_case_count}</b> <small style="color: var(--text-muted);">(CO:${c.cash_out_event_count}, Pred:${c.prediction_count})</small>
        </td>
        <td><small style="color: var(--text-muted); font-family: monospace;">${(c.time_window_start || "").substring(5, 16)} to ${(c.time_window_end || "").substring(11, 16)}</small></td>
        <td style="max-width: 260px;"><small style="color: #cbd5e1; line-height: 1.3; display: block;">${c.recommendation || c.recommended_action}</small></td>
      </tr>
      `;
    })
    .join("");
}

/**
 * Configure repeated convergence toolbar listeners (Feature 2).
 */
function setupConvergenceListeners() {
  const winSelect = document.getElementById("convWindowSelect");
  const typeSelect = document.getElementById("convTypeSelect");
  const minSelect = document.getElementById("convMinSelect");
  const refreshBtn = document.getElementById("btnRefreshConvergences");

  if (winSelect) winSelect.addEventListener("change", () => loadConvergences());
  if (typeSelect) typeSelect.addEventListener("change", () => loadConvergences());
  if (minSelect) minSelect.addEventListener("change", () => loadConvergences());
  if (refreshBtn) refreshBtn.addEventListener("click", () => loadConvergences());
}

/**
 * Fetch and refresh repeated spatial convergences from backend API.
 */
async function loadConvergences() {
  const winSelect = document.getElementById("convWindowSelect");
  const typeSelect = document.getElementById("convTypeSelect");
  const minSelect = document.getElementById("convMinSelect");

  const windowHours = winSelect ? parseInt(winSelect.value, 10) : 48;
  const targetType = typeSelect ? typeSelect.value : "all";
  const minMatches = minSelect ? parseInt(minSelect.value, 10) : 2;

  const summaryEl = document.getElementById("convergenceStatusSummary");
  if (summaryEl) summaryEl.innerText = `Scanning rolling ${windowHours}h window for repeated ATM and zone convergence...`;

  try {
    const data = await API.getConvergences({
      window_hours: windowHours,
      target_type: targetType,
      min_matches: minMatches,
    });
    renderConvergences(data);
    window.lastConvergencesData = data;
  } catch (err) {
    if (summaryEl) summaryEl.innerText = `Convergence detection error: ${err.message}`;
  }
}

/**
 * Render repeated spatial convergences into table and update badge count.
 */
function renderConvergences(data) {
  const badge = document.getElementById("convergenceBadgeCount");
  const summaryEl = document.getElementById("convergenceStatusSummary");
  const tbody = document.getElementById("convergenceTableBody");
  if (!tbody) return;

  const total = data.total_convergences || (data.convergences ? data.convergences.length : 0);
  if (badge) badge.innerText = total;

  if (summaryEl) {
    summaryEl.innerText = `Detected ${total} convergence pattern${total === 1 ? "" : "s"} (${data.atm_convergences_count || 0} ATM, ${data.zone_convergences_count || 0} Zone) across rolling ${data.window_hours || 48}h window (${data.window_start || ""} to ${data.window_end || ""}).`;
  }

  if (!data.convergences || data.convergences.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-dim); padding: 16px;">No repeated ATM or zone convergence detected in the selected time window.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.convergences
    .map(c => {
      const isAtm = c.convergence_type === "ATM_CONVERGENCE";
      const typeLabel = isAtm ? "Same ATM" : "Zone Corridor";
      const typeClass = isAtm ? "conv-type-atm" : "conv-type-zone";
      const sevClass = `priority-${(c.severity_level || "low").toLowerCase()}`;
      const atmsList = c.involved_atm_ids && c.involved_atm_ids.length > 0 ? c.involved_atm_ids.join(", ") : c.target_id;
      const targetDisplay = isAtm
        ? `<b>${c.target_id}</b> <small style="color: var(--text-muted);">(${c.zone_id.replace("ZONE_", "")})</small>`
        : `<b>${c.target_name}</b>`;

      return `
      <tr>
        <td><span class="cluster-id-badge">${c.convergence_id}</span></td>
        <td><span class="${typeClass}">${typeLabel}</span></td>
        <td>${targetDisplay}</td>
        <td><span class="priority-tag ${sevClass}">${c.severity_level}</span></td>
        <td><span class="cluster-score-pill">${c.convergence_score}/100</span></td>
        <td>
          <b>${c.total_matches}</b> <small style="color: var(--text-muted);">(Alerts:${c.prediction_count}, Cases:${c.case_count})</small>
        </td>
        <td><small style="color: var(--text-muted); font-family: monospace;">${atmsList}</small></td>
        <td><small style="color: var(--text-muted); font-family: monospace;">${c.time_span_hours}h span</small></td>
        <td style="max-width: 280px;">
          <small style="color: var(--text-main); font-weight: 500; display: block; line-height: 1.3; margin-bottom: 2px;">${escapeHtml(c.reason)}</small>
          <small style="color: var(--accent-teal); font-weight: 600; display: block; line-height: 1.25;">${escapeHtml(c.recommended_action)}</small>
        </td>
        <td>
          ${c.latitude && c.longitude ? `
            <button type="button" class="btn-conv-focus" onclick="window.focusMapCoordinates(${c.latitude}, ${c.longitude}, '${escapeHtml(c.target_id)}')">
              Map Pin
            </button>
          ` : "--"}
        </td>
      </tr>
      `;
    })
    .join("");
}

window.focusMapCoordinates = (lat, lon, targetId) => {
  if (MapController && typeof MapController.focusLocation === "function") {
    MapController.focusLocation(lat, lon, 15);
  }
  showToast(`Focused map on ${targetId}`, "info");
};

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
