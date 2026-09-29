/**
 * Main Application Controller for Cybercrime Predictive Analytics Dashboard.
 * Coordinates Geospatial Map, Chart Analytics, Prediction Workbench, Tabs, and Modal Audit.
 */

import { API, setActiveRole, getActiveRole } from "./api.js";
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
  setupPerformanceListeners();
  setupConsoleSwitcher();

  // Initialize Workflow Ribbon to Step 1: Complaint Intake
  setWorkflowStep(1);

  // 3. Load Core Telemetry & Data
  await loadDashboardData();

  // 4. Enforce active role console configuration
  applyConsoleMode(getActiveRole());
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

    // Load Intervention Performance & Operational Analytics (Feature)
    await loadInterventionPerformance();

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
      } else if (targetTabId === "tab-performance") {
        loadInterventionPerformance();
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
      if (result.case_id) {
        sessionStorage.setItem("citizen_active_case_id", result.case_id);
        startCitizenPolling(result.case_id);
      }
      renderPredictionResult(result);
      MapController.highlightPrediction(result.predicted_atm_id, result.top_candidates);

      // Refresh recent alert history and counters if permitted
      try {
        const updatedPredictions = await API.getPredictions(10);
        renderAlertHistory(updatedPredictions);
      } catch {}

      const kpiAlerts = document.getElementById("kpiAlerts");
      if (kpiAlerts) {
        const currentAlerts = parseInt(kpiAlerts.innerText.replace(/,/g, "") || "0", 10);
        kpiAlerts.innerText = (currentAlerts + 1).toLocaleString();
      }

      if (getActiveRole() === "investigator") {
        loadClusters();
        loadConvergences();
      }

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
 * Updates the 7-step SIH operational workflow ribbon state:
 * 1. Complaint, 2. Prediction, 3. Priority, 4. Map, 5. Convergence, 6. Dispatch, 7. Outcome
 */
function setWorkflowStep(stepIndex) {
  for (let i = 1; i <= 7; i++) {
    const el = document.getElementById(`wfStep${i}`);
    if (!el) continue;
    if (i < stepIndex) {
      el.className = "wf-step completed";
    } else if (i === stepIndex) {
      el.className = "wf-step active";
    } else {
      el.className = "wf-step";
    }
  }
}

/**
 * Maps raw operational outcome status to unified, truth-accurate display presentation.
 * Enforces strict distinction between spatial hits, corridor hits, false alerts,
 * no cashouts, and evasions. Never reports false alert or no cashout as a spatial hit.
 */
export function getOutcomeDetails(outcome, defaultPredictedAtm = "--") {
  if (!outcome) return null;
  const status = (outcome.outcome_status || "").trim().toUpperCase();

  if (status === "INTERCEPTED_AT_PREDICTED_ATM") {
    return {
      status,
      title: "Intercepted at Predicted ATM",
      badgeText: "INTERCEPTED AT PREDICTED ATM",
      badgeClass: "outcome-badge outcome-hit",
      spatialHitText: "Confirmed Spatial Hit",
      actualAtmText: outcome.actual_atm_id || defaultPredictedAtm,
      explanation: "Law enforcement field patrol intercepted suspect at calibrated target ATM location.",
      citizenExplanation: "Law enforcement field patrol successfully secured the target ATM corridor and intercepted unauthorized activity. Incident resolved.",
      isHit: true,
    };
  } else if (status === "INTERCEPTED_AT_OTHER_ATM") {
    return {
      status,
      title: "Intercepted at Other ATM",
      badgeText: "INTERCEPTED AT OTHER ATM",
      badgeClass: "outcome-badge outcome-other",
      spatialHitText: "Corridor / Adjacent Interception",
      actualAtmText: outcome.actual_atm_id || "--",
      explanation: "Suspect was intercepted at an alternate cash-out location along the transit corridor.",
      citizenExplanation: "Law enforcement intercepted unauthorized activity at an adjacent facility along the transit corridor. Incident resolved.",
      isHit: false,
    };
  } else if (status === "NO_CASHOUT") {
    return {
      status,
      title: "No Cash-Out Confirmed",
      badgeText: "NO CASH-OUT CONFIRMED",
      badgeClass: "outcome-badge outcome-false",
      spatialHitText: "No Attempt Detected",
      actualAtmText: outcome.actual_atm_id || "N/A (No Cashout)",
      explanation: "Patrol confirmed no physical cash withdrawal was attempted. Target account successfully restrained.",
      citizenExplanation: "Mule financial account successfully restrained; patrol confirmed zero unauthorized cash withdrawal occurred. Incident closed.",
      isHit: false,
    };
  } else if (status === "FALSE_ALERT") {
    return {
      status,
      title: "False Alert / Benign Activity",
      badgeText: "FALSE ALERT / BENIGN ACTIVITY",
      badgeClass: "outcome-badge outcome-false",
      spatialHitText: "Non-Fraud / Benign",
      actualAtmText: outcome.actual_atm_id || "N/A (Benign Activity)",
      explanation: "Investigation verified the transaction was benign or legitimate user activity.",
      citizenExplanation: "Investigation verified the reported activity as benign or legitimate transaction. Incident closed without adverse action.",
      isHit: false,
    };
  } else {
    return {
      status: status || "UNRESOLVED",
      title: "Unresolved",
      badgeText: "UNRESOLVED",
      badgeClass: "outcome-badge outcome-unresolved",
      spatialHitText: "Unresolved Intervention",
      actualAtmText: outcome.actual_atm_id || "Unknown / Unresolved",
      explanation: "Perimeter established but suspect was not intercepted or transaction could not be verified.",
      citizenExplanation: "Patrol unit established perimeter; no further unauthorized activity detected. Investigation closed.",
      isHit: false,
    };
  }
}

/**
 * Renders the Final Resolution / Case Outcome section for closed cases.
 * Completely replaces the active playbook area on both consoles.
 */
function renderFinalResolutionSection(result, role) {
  const resolutionSec = document.getElementById("caseFinalResolutionSection");
  if (!resolutionSec) return;
  resolutionSec.style.display = "block";

  const outcomeData = result._outcome || { outcome_status: "UNRESOLVED", notes: "Case resolution finalized." };
  const outDetails = getOutcomeDetails(outcomeData, result.predicted_atm_id);
  if (!outDetails) {
    resolutionSec.style.display = "none";
    return;
  }

  const dispUnit = result._dispatch?.patrol_unit_assigned || "PCR Unit";
  const notes = outcomeData.notes || "No debrief remarks recorded.";
  const resTimestamp = outcomeData.recorded_timestamp || outcomeData.outcome_timestamp || new Date().toISOString().replace("T", " ").substring(0, 19);

  if (role === "reporting") {
    // Reporting / Citizen Console: simple read-only final outcome
    resolutionSec.innerHTML = `
      <div class="resolution-container citizen-view">
        <div class="resolution-header">
          <div class="resolution-title-group">
            <svg class="btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="color: #10b981;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
            <span class="resolution-title">Official Case Resolution</span>
          </div>
          <span class="${outDetails.badgeClass}">${escapeHtml(outDetails.title)}</span>
        </div>
        <div class="resolution-explanation-banner">
          ${escapeHtml(outDetails.citizenExplanation)}
        </div>
        <div class="resolution-details-grid">
          <div class="res-cell">
            <span class="res-label">Case Status</span>
            <span class="res-value" style="color: #10b981; font-weight: 800;">CLOSED</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Target ATM</span>
            <span class="res-value font-mono">${escapeHtml(result.predicted_atm_id || '--')}</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Target Sector</span>
            <span class="res-value">${escapeHtml((result.predicted_zone_id || '').replace('ZONE_', 'Zone '))}</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Law Enforcement Unit</span>
            <span class="res-value font-mono">${escapeHtml(dispUnit)}</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Resolution Timestamp</span>
            <span class="res-value font-mono">${escapeHtml(resTimestamp)}</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Outcome Verification</span>
            <span class="res-value">${escapeHtml(outDetails.spatialHitText)}</span>
          </div>
        </div>
        <div class="resolution-footer-note">
          Law enforcement response concluded for Case ID: <b class="font-mono">${escapeHtml(result.case_id)}</b>. No further citizen action required.
        </div>
      </div>
    `;
  } else {
    // Investigator Console: Richer Final Resolution Audit Report
    const actions = (result.playbook && Array.isArray(result.playbook.actions)) ? result.playbook.actions : [
      { step: 1, title: "Patrol Unit Deployment", target: result.predicted_atm_id || "ATM" },
      { step: 2, title: "Transit Corridor Perimeter", target: result.predicted_zone_id || "Zone" },
      { step: 3, title: "Bank Nodal Liaison Lien", target: "Beneficiary Mule Account" },
      { step: 4, title: "Physical CCTV & Witness Evidence", target: "Facility Security Desk" }
    ];

    const auditActionsHtml = actions.map(a => `
      <div class="audit-action-item">
        <span><b>Step ${a.step}:</b> ${escapeHtml(a.title)} &bull; <span class="font-mono text-muted">${escapeHtml(a.target)}</span></span>
        <span class="priority-tag priority-low" style="font-size: 0.6rem;">EXECUTED</span>
      </div>
    `).join("");

    resolutionSec.innerHTML = `
      <div class="resolution-container investigator-view">
        <div class="resolution-header">
          <div class="resolution-title-group">
            <svg class="btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            <span class="resolution-title">Final Operational Resolution &amp; Audit Report</span>
            <span class="audit-lock-badge">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              Finalized &amp; Locked
            </span>
          </div>
          <span class="${outDetails.badgeClass}">${escapeHtml(outDetails.title)}</span>
        </div>
        <div class="resolution-explanation-banner">
          ${escapeHtml(outDetails.explanation)}
        </div>
        <div class="resolution-details-grid">
          <div class="res-cell">
            <span class="res-label">Case Status</span>
            <span class="res-value" style="color: var(--accent-teal); font-weight: 800;">CLOSED</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Prediction Verification</span>
            <span class="res-value font-bold">${escapeHtml(outDetails.spatialHitText)}</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Predicted ATM</span>
            <span class="res-value font-mono">${escapeHtml(result.predicted_atm_id || '--')}</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Actual Cashout ATM</span>
            <span class="res-value font-mono">${escapeHtml(outDetails.actualAtmText)}</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Dispatched Unit</span>
            <span class="res-value font-mono">${escapeHtml(dispUnit)}</span>
          </div>
          <div class="res-cell">
            <span class="res-label">Resolution Timestamp</span>
            <span class="res-value font-mono">${escapeHtml(resTimestamp)}</span>
          </div>
        </div>
        <div class="resolution-remarks-box">
          <div class="res-remarks-label">Investigator Debrief Remarks:</div>
          <div class="res-remarks-text">${escapeHtml(notes)}</div>
        </div>
        <details class="resolution-audit-accordion">
          <summary class="audit-summary">
            <span>Historical Tactical SOP Audit Trail</span>
            <span class="audit-count-hint">View executed SOP actions prior to closure &#9662;</span>
          </summary>
          <div class="audit-history-list">
            ${auditActionsHtml}
          </div>
        </details>
      </div>
    `;
  }
}

/**
 * Renders the role-appropriate playbook:
 * - Case Reporting / Citizen Console: "What You Should Do Now" victim safety guidance.
 * - Investigator Console: Law Enforcement Tactical SOP actions (PCR dispatch, cordon, nodal bank freeze).
 * - Closed Cases: Completely removes active playbook and displays Final Resolution section.
 */
function renderRolePlaybook(result, role) {
  const playbookCard = document.getElementById("playbookCard");
  const resolutionSec = document.getElementById("caseFinalResolutionSection");

  const isClosed = (result.case_status === "RESOLVED" || result.case_status === "CLOSED");
  if (isClosed) {
    if (playbookCard) playbookCard.style.display = "none";
    renderFinalResolutionSection(result, role);
    return;
  }

  if (resolutionSec) resolutionSec.style.display = "none";
  if (!playbookCard) return;
  const playbookTag = document.getElementById("playbookTag");
  const playbookTitle = document.getElementById("playbookTitle");
  const playbookBadge = document.getElementById("playbookDispositionBadge");
  const playbookSummary = document.getElementById("playbookSummary");
  const playbookList = document.getElementById("playbookActionsList");
  const copyBtn = document.getElementById("btnCopyDispatch");

  if (!playbookCard) return;

  if (role === "reporting") {
    // -------------------------------------------------------------------------
    // CITIZEN / REPORTING CONSOLE: "What You Should Do Now"
    // Short, victim-focused, exactly 3 immediate protection actions.
    // NO patrol deployment, CCTV, ATM surveillance, or police ops.
    // -------------------------------------------------------------------------
    playbookCard.style.display = "block";
    if (playbookTag) {
      playbookTag.innerText = "SAFETY";
      playbookTag.style.background = "#eff6ff";
      playbookTag.style.color = "#1d4ed8";
    }
    if (playbookTitle) playbookTitle.innerText = "What You Should Do Now";
    if (playbookBadge) {
      playbookBadge.innerText = "PROTECT YOURSELF / SECURE ACCOUNT";
      playbookBadge.className = "playbook-disposition-tag tag-citizen";
    }
    if (playbookSummary) {
      playbookSummary.className = "playbook-summary-banner banner-citizen";
      playbookSummary.innerText = "Immediate victim protection: take these 3 steps immediately to secure your bank account and preserve evidence for law enforcement.";
    }

    const citizenSteps = [
      {
        step: 1,
        urgency: "IMMEDIATE",
        stepBadge: "Step 1 · Immediate",
        title: "Contact Bank to Freeze Account & Cards",
        target: "Your Home Bank",
        oneLineSummary: "Immediately call your bank to place an emergency debit freeze or stop-payment on the compromised account or cards.",
        detail: "Contact your bank's 24/7 fraud reporting desk. Request an immediate freeze on all online transactions, UPI services, and debit cards linked to this account to prevent further withdrawals.",
      },
      {
        step: 2,
        urgency: "HIGH",
        stepBadge: "Step 2 · Urgent",
        title: "Report Unauthorized Transaction to Fraud Desk",
        target: "Bank Fraud Helpline",
        oneLineSummary: "Formally dispute unauthorized transactions with the transaction reference ID (UPI / IMPS / NEFT) to initiate inter-bank hold.",
        detail: "Provide your bank with exact transaction timestamps, amounts, and dispute reference numbers. Ask the fraud team to notify the beneficiary bank's nodal officer to freeze incoming funds in transit.",
      },
      {
        step: 3,
        urgency: "STANDARD",
        stepBadge: "Step 3 · Evidence",
        title: "Preserve Transaction SMS & Screenshots as Evidence",
        target: `Case Record: ${result.case_id || 'Reference'}`,
        oneLineSummary: "Save debit SMS notifications, transaction receipts, bank statements, and chat records as official evidence for investigators.",
        detail: "Retain uncropped digital proof including caller numbers, payment confirmation screens, and SMS timestamps. Investigating cybercrime units require these artifacts to link the fraudulent cash-out.",
      },
    ];

    if (playbookList) {
      playbookList.innerHTML = citizenSteps
        .slice(0, 3)
        .map(action => `
          <div class="playbook-action-card compact" id="action-step-${action.step}">
            <div class="playbook-card-header">
              <div class="playbook-header-left">
                <span class="playbook-step-badge urgency-${action.urgency.toLowerCase()}">${escapeHtml(action.stepBadge)}</span>
                <span class="playbook-action-title">${escapeHtml(action.title)}</span>
              </div>
              <span class="playbook-action-target target-citizen">${escapeHtml(action.target)}</span>
            </div>
            <div class="playbook-action-desc">${escapeHtml(action.oneLineSummary)}</div>
            <details class="playbook-action-expandable">
              <summary class="playbook-expandable-summary">Details &amp; Rationale</summary>
              <div class="playbook-expandable-content">${escapeHtml(action.detail)}</div>
            </details>
          </div>
        `)
        .join("");
    }

    if (copyBtn) {
      const text = document.getElementById("copyBriefText");
      if (text) text.innerText = "Copy Citizen Guidance";
      copyBtn.onclick = async () => {
        const textToCopy = `[CYBERCRIME CITIZEN ADVISORY - CASE ${result.case_id || '--'}]\n1. Freeze Account: Contact bank immediately to freeze compromised accounts and cards.\n2. Report Fraud: Call official bank fraud helpline and register formal transaction dispute.\n3. Preserve Evidence: Save all debit SMS alerts, receipts, and communication logs.`;
        try {
          await navigator.clipboard.writeText(textToCopy);
          const iconSvg = document.getElementById("copyBriefIconSvg");
          if (iconSvg) iconSvg.innerHTML = `<polyline points="20 6 9 17 4 12"/>`;
          if (text) text.innerText = "Copied!";
          copyBtn.classList.add("copied");
          showToast("Citizen safety guidance copied to clipboard!", "success");
          setTimeout(() => {
            if (iconSvg) iconSvg.innerHTML = `<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>`;
            if (text) text.innerText = "Copy Citizen Guidance";
            copyBtn.classList.remove("copied");
          }, 2500);
        } catch (e) {
          showToast("Failed to copy guidance: " + e.message, "error");
        }
      };
    }
  } else {
    // -------------------------------------------------------------------------
    // INVESTIGATOR / OPERATIONS CONSOLE: "Tactical Action Playbook"
    // Short, operational law enforcement SOP, exactly 3 actions.
    // NO bank freezing, OTP warnings, or citizen protection tasks.
    // -------------------------------------------------------------------------
    playbookCard.style.display = "block";
    if (playbookTag) {
      playbookTag.innerText = "SOP";
      playbookTag.style.background = "#f0fdfa";
      playbookTag.style.color = "var(--accent-teal-dark)";
    }
    if (playbookTitle) playbookTitle.innerText = "Tactical Action Playbook (Law Enforcement)";
    if (playbookBadge) {
      playbookBadge.innerText = "RESPOND / INTERVENE / VERIFY OUTCOME";
      playbookBadge.className = "playbook-disposition-tag tag-investigator";
    }

    const predAtm = result.predicted_atm_id || "ATM";
    const zoneName = (result.predicted_zone_id || "Zone").replace("ZONE_", "Zone ");
    const winStr = (result.predicted_window_start && result.predicted_window_end)
      ? `${result.predicted_window_start.substring(11, 16)} - ${result.predicted_window_end.substring(11, 16)} hrs`
      : "Immediate 45-min Window";
    const cands = (Array.isArray(result.top_candidates) && result.top_candidates.length > 1)
      ? result.top_candidates.slice(1, 3).map(c => c.atm_id).join(", ")
      : "adjacent sector terminals";

    if (playbookSummary) {
      playbookSummary.className = "playbook-summary-banner banner-investigator";
      playbookSummary.innerText = `Tactical interdiction SOP: coordinate field patrol interdiction at ${predAtm} (${zoneName}), screen corridor candidates, and record verified outcome.`;
    }

    const investigatorSteps = [
      {
        step: 1,
        urgency: "IMMEDIATE",
        stepBadge: "Step 1 · Dispatch",
        title: "Dispatch Field Patrol to Target ATM",
        target: `${predAtm} (${zoneName})`,
        oneLineSummary: `Position nearest mobile PCR / beat patrol at ${predAtm} within ${winStr} to interdict cash withdrawal runner.`,
        detail: `Deploy sector unit to establish discreet visual perimeter around ${predAtm}. Monitor kiosk for individuals attempting multiple card withdrawals, wearing full helmets/masks, or loitering near terminal during ${winStr}.`,
      },
      {
        step: 2,
        urgency: "HIGH",
        stepBadge: "Step 2 · Interdiction",
        title: "Prioritize Target ATM & Screen Candidate Corridor",
        target: `Corridor: ${cands}`,
        oneLineSummary: `Monitor ${predAtm} and alert adjoining beat units to screen secondary ranked ATMs (${cands}) and review facility CCTV feeds.`,
        detail: `If suspect runner encounters physical security at ${predAtm}, spatial convergence indicates immediate diversion to top cluster candidates (${cands}). Task beat staff to verify CCTV feeds and observe adjoining ATM perimeters.`,
      },
      {
        step: 3,
        urgency: "STANDARD",
        stepBadge: "Step 3 · Outcome",
        title: "Record Verified Field Outcome & Close Incident",
        target: "Case Terminal Resolution",
        oneLineSummary: "Log interdiction result (intercepted runner, no cash-out, or false alert) to lock audit log and finalize case lifecycle.",
        detail: "Following field unit debrief, click 'Record Outcome' in the control bar above. Enter the verified actual ATM and operational remarks to lock evidence and transition case to CLOSED.",
      },
    ];

    if (playbookList) {
      playbookList.innerHTML = investigatorSteps
        .slice(0, 3)
        .map(action => `
          <div class="playbook-action-card compact" id="action-step-${action.step}">
            <div class="playbook-card-header">
              <div class="playbook-header-left">
                <span class="playbook-step-badge urgency-${action.urgency.toLowerCase()}">${escapeHtml(action.stepBadge)}</span>
                <span class="playbook-action-title">${escapeHtml(action.title)}</span>
              </div>
              <span class="playbook-action-target">${escapeHtml(action.target)}</span>
            </div>
            <div class="playbook-action-desc">${escapeHtml(action.oneLineSummary)}</div>
            <details class="playbook-action-expandable">
              <summary class="playbook-expandable-summary">Details &amp; Rationale</summary>
              <div class="playbook-expandable-content">${escapeHtml(action.detail)}</div>
            </details>
          </div>
        `)
        .join("");
    }

    if (copyBtn) {
      const text = document.getElementById("copyBriefText");
      if (text) text.innerText = "Copy Tactical Brief";
      copyBtn.onclick = async () => {
        const textToCopy = `[TACTICAL SOP BRIEF] Case: ${result.case_id || '--'} | Priority: ${result.priority_level || 'MED'} (${result.priority_score || 0}/100)\nTarget ATM: ${predAtm} (${zoneName}) | Window: ${winStr}\n1. Dispatch patrol to ${predAtm} within operational window.\n2. Screen secondary cluster terminals (${cands}) & preserve CCTV.\n3. Log field debrief and record verified outcome.`;
        try {
          await navigator.clipboard.writeText(textToCopy);
          const iconSvg = document.getElementById("copyBriefIconSvg");
          if (iconSvg) iconSvg.innerHTML = `<polyline points="20 6 9 17 4 12"/>`;
          if (text) text.innerText = "Copied!";
          copyBtn.classList.add("copied");
          showToast("Tactical Dispatch Brief copied to clipboard!", "success");
          setTimeout(() => {
            if (iconSvg) iconSvg.innerHTML = `<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>`;
            if (text) text.innerText = "Copy Tactical Brief";
            copyBtn.classList.remove("copied");
          }, 2500);
        } catch (e) {
          showToast("Failed to copy brief: " + e.message, "error");
        }
      };
    }
  }
}

/**
 * Render predictive inference results to the output card.
 */
function renderPredictionResult(result) {
  const placeholder = document.getElementById("forecastCardPlaceholder");
  if (placeholder) placeholder.style.display = "none";

  const card = document.getElementById("forecastCard");
  if (!card) return;
  card.style.display = "block";

  // Advance workflow ribbon: Complaint, Prediction, Priority, Map active
  setWorkflowStep(4);

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

  // Alert Deduplication & Escalation Lifecycle State
  const alertStateBadge = document.getElementById("predAlertStateBadge");
  const lifecycleNote = document.getElementById("predAlertLifecycleNote");
  const lifecycleText = document.getElementById("predAlertLifecycleText");
  const state = (result.alert_state || "NEW").toUpperCase();
  const occCount = result.occurrence_count || 1;

  if (alertStateBadge) {
    alertStateBadge.className = `alert-state-badge state-${state.toLowerCase()}`;
    if (state === "NEW") {
      alertStateBadge.innerText = "NEW ALERT";
    } else if (state === "REFRESHED") {
      alertStateBadge.innerText = `REFRESHED (${occCount}x)`;
    } else if (state === "ESCALATED") {
      alertStateBadge.innerText = `ESCALATED (${occCount}x)`;
    }
  }

  if (lifecycleNote && lifecycleText) {
    if (state === "ESCALATED") {
      lifecycleNote.className = "alert-lifecycle-banner banner-escalated";
      lifecycleNote.style.display = "flex";
      lifecycleText.innerText = result.escalation_reason || "Alert escalated: High-velocity convergence or material priority surge detected.";
    } else if (state === "REFRESHED") {
      lifecycleNote.className = "alert-lifecycle-banner";
      lifecycleNote.style.display = "flex";
      lifecycleText.innerText = result.escalation_reason || `Alert refreshed: Subsequent incident deduplicated at target ATM (${occCount} occurrences). Risk profile stable.`;
    } else {
      lifecycleNote.style.display = "none";
    }
  }

  // Operational Case Lifecycle & Patrol Dispatch (Feature: Dispatch Routing & Evidence Export)
  window.currentActivePrediction = result;
  const caseIdBadge = document.getElementById("predCaseIdBadge");
  const caseStatusBadge = document.getElementById("predCaseStatusBadge");
  const dispatchBadge = document.getElementById("predDispatchBadge");
  const outcomeBadge = document.getElementById("predOutcomeBadge");
  const btnTransition = document.getElementById("btnCaseTransition");
  const transitionText = document.getElementById("caseTransitionText");
  const btnViewDispatch = document.getElementById("btnViewDispatch");
  const btnRecordOutcome = document.getElementById("btnRecordOutcome");
  const btnExportEvidence = document.getElementById("btnExportEvidence");
  const evidenceDropdown = document.getElementById("evidenceDropdown");
  const btnExportJson = document.getElementById("btnExportJson");
  const btnExportCsv = document.getElementById("btnExportCsv");

  function updateCaseControls(caseId, status, dispatchInfo = null, outcomeInfo = null) {
    if (dispatchInfo) result._dispatch = dispatchInfo;
    if (outcomeInfo) result._outcome = outcomeInfo;
    if (status) result.case_status = status;
    const currentDisp = dispatchInfo || result._dispatch || null;
    const currentOut = outcomeInfo || result._outcome || null;
    const role = getActiveRole();
    const citizenNotice = document.getElementById("citizenTrackingNotice");

    renderRolePlaybook(result, role);

    if (caseIdBadge) {
      if (caseId) {
        caseIdBadge.innerText = caseId;
        caseIdBadge.style.display = "inline-flex";
      } else {
        caseIdBadge.style.display = "none";
      }
    }
    if (caseStatusBadge) {
      if (status) {
        let statusLabel = status.replace(/_/g, " ");
        let badgeClass = `case-status-badge status-${status.toLowerCase()}`;
        if (status === "RESOLVED" || status === "CLOSED") {
          statusLabel = "CLOSED";
          badgeClass = "case-status-badge status-closed";
        }
        caseStatusBadge.innerText = `CASE STATUS: ${statusLabel}`;
        caseStatusBadge.className = badgeClass;
        caseStatusBadge.style.display = "inline-flex";
      } else {
        caseStatusBadge.style.display = "none";
      }
    }

    if (dispatchBadge) {
      if (!caseId) {
        dispatchBadge.style.display = "none";
      } else if (role === "reporting") {
        if (status === "PATROL_DISPATCHED" || status === "OUTCOME_PENDING") {
          dispatchBadge.innerText = "POLICE PATROL DISPATCHED";
          dispatchBadge.className = "dispatch-badge status-dispatched";
          dispatchBadge.style.display = "inline-flex";
        } else if (status === "RESOLVED" || status === "CLOSED") {
          dispatchBadge.innerText = "INTERVENTION COMPLETED";
          dispatchBadge.className = "dispatch-badge status-dispatched";
          dispatchBadge.style.display = "inline-flex";
        } else {
          dispatchBadge.innerText = "POLICE ACTION PENDING";
          dispatchBadge.className = "dispatch-badge";
          dispatchBadge.style.display = "inline-flex";
        }
      } else if (status === "PATROL_DISPATCHED" || status === "OUTCOME_PENDING") {
        const unitName = currentDisp?.patrol_unit_assigned || "PCR";
        dispatchBadge.innerText = `${unitName}: DISPATCHED`;
        dispatchBadge.className = "dispatch-badge status-dispatched";
        dispatchBadge.style.display = "inline-flex";
      } else if (status === "RESOLVED" || status === "CLOSED") {
        const unitName = currentDisp?.patrol_unit_assigned || "PCR";
        dispatchBadge.innerText = `${unitName}: COMPLETED`;
        dispatchBadge.className = "dispatch-badge status-dispatched";
        dispatchBadge.style.display = "inline-flex";
      } else {
        dispatchBadge.innerText = "DISPATCH: READY";
        dispatchBadge.className = "dispatch-badge";
        dispatchBadge.style.display = "inline-flex";
      }
    }

    const outDetails = getOutcomeDetails(currentOut, result.predicted_atm_id);

    if (outcomeBadge) {
      if (!caseId || !outDetails) {
        outcomeBadge.style.display = "none";
      } else {
        const isClosed = (status === "RESOLVED" || status === "CLOSED");
        outcomeBadge.className = outDetails.badgeClass;
        outcomeBadge.innerText = (isClosed ? "FINAL OUTCOME: " : "OUTCOME: ") + outDetails.badgeText;
        outcomeBadge.style.display = "inline-flex";
      }
    }

    // Final Resolution Report Card in Hero: Keep hidden so #caseFinalResolutionSection cleanly replaces the active playbook
    const heroReportCard = document.getElementById("heroFinalOutcomeRecord");
    if (heroReportCard) {
      heroReportCard.style.display = "none";
    }

    // Role-specific operational button enforcement
    if (role === "reporting") {
      if (btnTransition) btnTransition.style.display = "none";
      if (btnRecordOutcome) btnRecordOutcome.style.display = "none";
      if (btnViewDispatch) btnViewDispatch.style.display = "none";
      if (btnExportEvidence) btnExportEvidence.style.display = "none";

      if (citizenNotice && caseId) {
        citizenNotice.style.display = "flex";
        const cNum = document.getElementById("citizenTrackingNumber");
        if (cNum) cNum.innerText = caseId;
        const cText = document.getElementById("citizenTrackingText");
        if (cText) {
          if (status === "PATROL_DISPATCHED") {
            cText.innerText = "Law Enforcement Update: Active patrol unit dispatched to secure predicted cash-out corridor.";
          } else if (status === "OUTCOME_PENDING") {
            cText.innerText = "Law Enforcement Update: Patrol on-scene at cash-out zone • Interdiction operation in progress.";
          } else if (status === "RESOLVED" || status === "CLOSED") {
            cText.innerText = "Law Enforcement Update: Operational response concluded • Official case resolution recorded below.";
          } else {
            cText.innerText = `Complaint Logged (${caseId}) • Incident queued in Law Enforcement operational dispatch terminal.`;
          }
        }
      }
      return;
    }

    // Investigator Console State Machine Controls
    if (citizenNotice) citizenNotice.style.display = "none";

    if (!caseId) {
      if (btnTransition) btnTransition.style.display = "none";
      if (btnRecordOutcome) btnRecordOutcome.style.display = "none";
      if (btnViewDispatch) btnViewDispatch.style.display = "none";
      if (btnExportEvidence) btnExportEvidence.style.display = "none";
      return;
    }

    if (btnExportEvidence) {
      btnExportEvidence.style.display = "inline-flex";
    }

    if (status === "NEW_ALERT") {
      // 1. NEW_ALERT: Primary control is "Dispatch Patrol"
      if (btnTransition) {
        btnTransition.style.display = "inline-flex";
        btnTransition.disabled = false;
        btnTransition.style.opacity = "1";
        btnTransition.style.cursor = "pointer";
        btnTransition.className = "btn-op-primary";
        btnTransition.innerHTML = `<svg class="btn-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg><span id="caseTransitionText">Dispatch Patrol</span>`;
      }
      if (btnRecordOutcome) btnRecordOutcome.style.display = "none";
      if (btnViewDispatch) btnViewDispatch.style.display = "none";
    } else if (status === "PATROL_DISPATCHED" || status === "OUTCOME_PENDING") {
      // 2. PATROL_DISPATCHED / OUTCOME_PENDING: Primary action is "Log Outcome" / "Record Outcome & Close"
      if (btnTransition) {
        btnTransition.style.display = "none";
      }
      if (btnRecordOutcome) {
        btnRecordOutcome.style.display = "inline-flex";
        btnRecordOutcome.disabled = false;
        btnRecordOutcome.className = "btn-op-primary";
        const actionLabel = status === "OUTCOME_PENDING" ? "Record Outcome & Close" : "Log Outcome";
        btnRecordOutcome.innerHTML = `<svg class="btn-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="m9 14 2 2 4-4"/></svg><span id="recordOutcomeText">${actionLabel}</span>`;
        btnRecordOutcome.title = "Record Actual Incident Outcome";
      }
      if (btnViewDispatch) {
        btnViewDispatch.style.display = "inline-flex";
        btnViewDispatch.className = "btn-op-secondary";
        btnViewDispatch.title = "View Field Dispatch Details";
      }
    } else if (status === "RESOLVED" || status === "CLOSED") {
      // 3. RESOLVED / CLOSED: Terminal state, read-only
      if (btnTransition) {
        btnTransition.style.display = "none";
      }
      if (btnRecordOutcome) {
        btnRecordOutcome.style.display = "inline-flex";
        btnRecordOutcome.className = "btn-op-secondary";
        btnRecordOutcome.innerHTML = `<svg class="btn-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg><span>View Final Outcome</span>`;
        btnRecordOutcome.title = "View Final Recorded Outcome (Read-Only)";
      }
      if (btnViewDispatch) {
        btnViewDispatch.style.display = "inline-flex";
        btnViewDispatch.className = "btn-op-secondary";
        btnViewDispatch.title = "View Field Dispatch Details (Read-Only)";
      }
    }
  }

  window._currentUpdateCaseControls = updateCaseControls;
  updateCaseControls(result.case_id, result.case_status);

  // Load existing dispatch if case already has one
  if (result.case_id && (result.case_status === "PATROL_DISPATCHED" || result.case_status === "OUTCOME_PENDING" || result.case_status === "RESOLVED" || result.case_status === "CLOSED")) {
    API.getCaseDispatch(result.case_id)
      .then(disp => {
        if (disp) updateCaseControls(result.case_id, result.case_status, disp, null);
      })
      .catch(() => {});
  }

  // Load existing outcome if case already has one
  if (result.case_id) {
    API.getCaseOutcome(result.case_id)
      .then(outcome => {
        if (outcome) updateCaseControls(result.case_id, result.case_status, null, outcome);
      })
      .catch(() => {});
  }

  // Action: Launch Dispatch (NEW_ALERT state only)
  if (btnTransition) {
    btnTransition.onclick = async () => {
      openDispatchModal(result);
    };
  }

  // Action: Open Dispatch Details Modal directly
  if (btnViewDispatch) {
    btnViewDispatch.onclick = () => {
      openDispatchModal(result);
    };
  }

  // Action: Open Outcome Logging Modal directly
  if (btnRecordOutcome) {
    btnRecordOutcome.onclick = () => {
      openOutcomeModal(result);
    };
  }

  // Action: Evidence Export Controls
  if (btnExportEvidence) {
    btnExportEvidence.onclick = (e) => {
      e.stopPropagation();
      if (evidenceDropdown) {
        evidenceDropdown.style.display = evidenceDropdown.style.display === "block" ? "none" : "block";
      }
    };
  }

  if (btnExportJson) {
    btnExportJson.onclick = (e) => {
      e.preventDefault();
      if (evidenceDropdown) evidenceDropdown.style.display = "none";
      if (!result.case_id) return;
      window.location.href = API.getEvidenceDownloadUrl(result.case_id, "json");
      showToast(`Downloading JSON evidence packet for case ${result.case_id}`, "info");
    };
  }

  if (btnExportCsv) {
    btnExportCsv.onclick = (e) => {
      e.preventDefault();
      if (evidenceDropdown) evidenceDropdown.style.display = "none";
      if (!result.case_id) return;
      window.location.href = API.getEvidenceDownloadUrl(result.case_id, "csv");
      showToast(`Downloading CSV evidence packet for case ${result.case_id}`, "info");
    };
  }

  // Dismiss dropdown on outside click
  window.addEventListener("click", () => {
    if (evidenceDropdown && evidenceDropdown.style.display === "block") {
      evidenceDropdown.style.display = "none";
    }
  });

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
    const isClosed = (result.case_status === "RESOLVED" || result.case_status === "CLOSED");
    if (isClosed) {
      heroActionEl.innerText = (getActiveRole() === "reporting")
        ? "Case resolution finalized by law enforcement. View official case outcome details below."
        : "Operational response concluded. Outcome recorded and case closed. Review resolution audit report below.";
    } else if (getActiveRole() === "reporting") {
      heroActionEl.innerText = "Citizen Guidance: Protect yourself & secure your account. Contact your bank immediately to freeze compromised cards/accounts and preserve evidence.";
    } else {
      const predAtm = result.predicted_atm_id || "target ATM";
      const winStr = (result.predicted_window_start && result.predicted_window_end)
        ? `${result.predicted_window_start.substring(11, 16)} - ${result.predicted_window_end.substring(11, 16)} hrs`
        : "operational window";
      heroActionEl.innerText = `Tactical Directive: Respond, intervene & verify outcome. Dispatch field patrol to secure ${predAtm} within ${winStr}.`;
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

  // Role-appropriate Action Playbook (Citizen Safety Guidance vs Police Tactical SOP)
  renderRolePlaybook(result, getActiveRole());

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
 * Fetch and refresh recent alerts.
 */
async function loadAlertHistory() {
  try {
    const predictions = await API.getPredictions(10);
    renderAlertHistory(predictions);
  } catch (err) {
    console.error("Failed to load alert history:", err);
  }
}

/**
 * Render recent prediction alerts to the dispatch audit log.
 */
function renderAlertHistory(predictions) {
  const container = document.getElementById("alertHistoryBody");
  if (!container) return;

  if (!predictions || predictions.length === 0) {
    container.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 12px;">No recent alerts generated.</td></tr>`;
    return;
  }

  container.innerHTML = predictions
    .map(p => {
      const pLevel = (p.priority_level || p.risk_level || "LOW").toUpperCase();
      const pScore = typeof p.priority_score === "number" ? p.priority_score : null;
      const state = (p.alert_state || "NEW").toUpperCase();
      const occCount = p.occurrence_count || 1;
      const stateBadge = `<span class="alert-state-badge state-${state.toLowerCase()}" title="${escapeHtml(p.escalation_reason || '')}">${state}${occCount > 1 ? ` (${occCount}x)` : ""}</span>`;
      const caseStatus = (p.case_status || "NEW_ALERT").toUpperCase();
      const caseBadge = p.case_id 
        ? `<span class="case-id-badge">${escapeHtml(p.case_id)}</span>` 
        : `<span style="color: var(--text-dim); font-size: 0.72rem;">—</span>`;
      const statusBadge = `<span class="case-status-badge status-${caseStatus.toLowerCase()}">${caseStatus}</span>`;

      return `
      <tr>
        <td><small style="color: var(--text-muted); font-family: monospace;">${p.prediction_timestamp ? p.prediction_timestamp.substring(11, 19) : ""}</small></td>
        <td>${caseBadge}</td>
        <td><b style="color: var(--accent-blue);">${p.predicted_atm_id}</b></td>
        <td>${stateBadge}</td>
        <td>${statusBadge}</td>
        <td>${p.predicted_zone_id.replace("ZONE_", "")}</td>
        <td>
          <span class="priority-tag priority-${pLevel.toLowerCase()}">
            ${pScore !== null ? `${pScore} · ` : ""}${pLevel}
          </span>
        </td>
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
    if (MapController && typeof MapController.renderConvergences === "function") {
      MapController.renderConvergences(data);
    }
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
            <button type="button" class="btn-conv-focus" onclick="window.viewConvergenceOnMap('${escapeHtml(c.convergence_id)}')">
              View on Map
            </button>
          ` : "--"}
        </td>
      </tr>
      `;
    })
    .join("");
}

window.viewConvergenceOnMap = (convergenceId) => {
  if (MapController && typeof MapController.focusConvergenceById === "function") {
    const focused = MapController.focusConvergenceById(convergenceId);
    if (focused) {
      const mapPanel = document.querySelector(".map-panel");
      if (mapPanel) {
        mapPanel.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      showToast(`Focused map on convergence ${convergenceId}`, "info");
      return;
    }
  }
  showToast(`Convergence ${convergenceId} not found on map`, "error");
};

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

  setupDispatchModalListeners();
  setupOutcomeModalListeners();
}

/**
 * Opens and populates the Field Patrol Dispatch modal.
 */
async function openDispatchModal(result) {
  const modal = document.getElementById("dispatchModal");
  if (!modal || !result.case_id) return;

  const caseIdEl = document.getElementById("dispModalCaseId");
  const dispatchIdEl = document.getElementById("dispModalDispatchId");
  const caseStatusEl = document.getElementById("dispModalCaseStatus");
  const dispStatusEl = document.getElementById("dispModalDispatchStatus");
  const atmEl = document.getElementById("dispModalAtm");
  const zoneEl = document.getElementById("dispModalZone");
  const priorityEl = document.getElementById("dispModalPriority");
  const windowEl = document.getElementById("dispModalWindow");
  const unitInput = document.getElementById("dispModalUnitInput");
  const notesInput = document.getElementById("dispModalNotesInput");
  const briefEl = document.getElementById("dispModalTacticalBrief");
  const confirmBtn = document.getElementById("btnConfirmDispatchModal");

  caseIdEl.innerText = result.case_id;
  atmEl.innerText = result.predicted_atm_id || "--";
  zoneEl.innerText = (result.predicted_zone_id || "--").replace("ZONE_", "Zone ");
  priorityEl.innerText = `${result.priority_level || "MEDIUM"} (${result.priority_score || 50}/100)`;

  let leadWin = "Immediate Intercept Window";
  if (result.predicted_window_start && result.predicted_window_end) {
    leadWin = `${result.predicted_window_start.substring(11, 16)} – ${result.predicted_window_end.substring(11, 16)} hrs`;
  }
  windowEl.innerText = leadWin;

  const defaultUnit = `PCR-${(result.predicted_zone_id || "ZONE").replace("ZONE_", "")}-01`;
  unitInput.value = defaultUnit;
  notesInput.value = "";

  const defaultBrief = (result.playbook && (result.playbook.dispatch_brief || result.playbook.summary)) ||
    `[TACTICAL BRIEF] Priority: ${result.priority_level} | Target ATM: ${result.predicted_atm_id} (${zoneEl.innerText}) | Window: ${leadWin}`;
  briefEl.innerText = defaultBrief;

  // Try to load existing dispatch if any
  try {
    const existing = await API.getCaseDispatch(result.case_id);
    if (existing) {
      dispatchIdEl.innerText = existing.dispatch_id;
      dispStatusEl.innerText = existing.dispatch_status;
      dispStatusEl.className = `dispatch-badge status-${existing.dispatch_status.toLowerCase()}`;
      if (existing.patrol_unit_assigned) unitInput.value = existing.patrol_unit_assigned;
      if (existing.tactical_brief) briefEl.innerText = existing.tactical_brief;
      caseStatusEl.innerText = result.case_status || "PATROL_DISPATCHED";
      caseStatusEl.className = `case-status-badge status-${(result.case_status || "patrol_dispatched").toLowerCase()}`;

      // View-only if already dispatched
      if (existing.dispatch_status === "DISPATCHED" || result.case_status !== "NEW_ALERT") {
        unitInput.disabled = true;
        notesInput.disabled = true;
        confirmBtn.style.display = "none";
      } else {
        unitInput.disabled = false;
        notesInput.disabled = false;
        confirmBtn.style.display = "inline-flex";
        confirmBtn.innerText = "Dispatch Unit";
      }
    }
  } catch (err) {
    dispatchIdEl.innerText = "NOT_DISPATCHED";
    dispStatusEl.innerText = "READY";
    dispStatusEl.className = "dispatch-badge";
    caseStatusEl.innerText = result.case_status || "NEW_ALERT";
    caseStatusEl.className = `case-status-badge status-${(result.case_status || "new_alert").toLowerCase()}`;
    unitInput.disabled = false;
    notesInput.disabled = false;
    confirmBtn.style.display = "inline-flex";
    confirmBtn.innerText = "Confirm & Dispatch";
  }

  modal.style.display = "flex";
}

function setupDispatchModalListeners() {
  const modal = document.getElementById("dispatchModal");
  const closeBtn = document.getElementById("closeDispatchModalBtn");
  const cancelBtn = document.getElementById("btnCancelDispatchModal");
  const confirmBtn = document.getElementById("btnConfirmDispatchModal");
  const unitInput = document.getElementById("dispModalUnitInput");
  const notesInput = document.getElementById("dispModalNotesInput");

  if (!modal) return;

  const closeModal = () => {
    modal.style.display = "none";
  };

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

  window.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.style.display === "flex") {
      closeModal();
    }
  });

  if (confirmBtn) {
    confirmBtn.addEventListener("click", async () => {
      const res = window.currentActivePrediction;
      if (!res || !res.case_id) return;
      const unit = unitInput.value.trim() || `PCR-${(res.predicted_zone_id || "ZONE").replace("ZONE_", "")}-01`;
      const notes = notesInput.value.trim();

      confirmBtn.disabled = true;
      const origText = confirmBtn.innerText;
      confirmBtn.innerText = "Dispatching...";
      try {
        const disp = await API.dispatchPatrol(res.case_id, {
          patrol_unit: unit,
          notes: notes,
          auto_advance_case: true,
        });
        res.case_status = "PATROL_DISPATCHED";
        res._dispatch = disp;
        closeModal();
        showToast(`Field patrol unit ${disp.patrol_unit_assigned} dispatched (ID: ${disp.dispatch_id})`, "success");

        // Immediately update sequential operational state
        const caseStatusBadge = document.getElementById("predCaseStatusBadge");
        if (caseStatusBadge) {
          caseStatusBadge.innerText = "CASE STATUS: PATROL DISPATCHED";
          caseStatusBadge.className = "case-status-badge status-patrol_dispatched";
        }
        const dispatchBadge = document.getElementById("predDispatchBadge");
        if (dispatchBadge) {
          dispatchBadge.innerText = `${disp.patrol_unit_assigned}: DISPATCHED`;
          dispatchBadge.className = "dispatch-badge status-dispatched";
        }
        const btnTransition = document.getElementById("btnCaseTransition");
        if (btnTransition) btnTransition.style.display = "none";

        const btnRecordOutcome = document.getElementById("btnRecordOutcome");
        if (btnRecordOutcome) {
          btnRecordOutcome.style.display = "inline-flex";
          btnRecordOutcome.className = "btn-op-primary";
          btnRecordOutcome.innerHTML = `<svg class="btn-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="m9 14 2 2 4-4"/></svg><span id="recordOutcomeText">Log Outcome</span>`;
          btnRecordOutcome.title = "Record Actual Incident Outcome";
        }
        const btnViewDispatch = document.getElementById("btnViewDispatch");
        if (btnViewDispatch) {
          btnViewDispatch.style.display = "inline-flex";
          btnViewDispatch.className = "btn-op-secondary";
        }

        await loadAlertHistory();
        loadInterventionPerformance();
        setWorkflowStep(6);
      } catch (err) {
        showToast(`Failed to dispatch patrol: ${err.message}`, "error");
      } finally {
        confirmBtn.disabled = false;
        confirmBtn.innerText = origText;
      }
    });
  }
}

/**
 * Opens and populates the Incident Outcome & Feedback modal.
 */
async function openOutcomeModal(result) {
  const modal = document.getElementById("outcomeModal");
  if (!modal || !result.case_id) return;

  const caseIdEl = document.getElementById("outcomeModalCaseId");
  const predAtmEl = document.getElementById("outcomeModalPredictedAtm");
  const caseStatusEl = document.getElementById("outcomeModalCurrentStatus");
  const unitEl = document.getElementById("outcomeModalUnit");
  const statusSelect = document.getElementById("outcomeStatusSelect");
  const actualAtmInput = document.getElementById("outcomeActualAtmInput");
  const notesInput = document.getElementById("outcomeNotesInput");
  const feedbackText = document.getElementById("outcomeHitFeedbackText");
  const feedbackBanner = document.getElementById("outcomeHitFeedback");
  const confirmBtn = document.getElementById("btnConfirmOutcomeModal");

  caseIdEl.innerText = result.case_id;
  predAtmEl.innerText = result.predicted_atm_id || "--";
  caseStatusEl.innerText = result.case_status || "PATROL_DISPATCHED";
  caseStatusEl.className = `case-status-badge status-${(result.case_status || "patrol_dispatched").toLowerCase()}`;

  actualAtmInput.value = result.predicted_atm_id || "";
  notesInput.value = "";
  statusSelect.value = "INTERCEPTED_AT_PREDICTED_ATM";

  function updateFeedbackBanner() {
    const val = statusSelect.value;
    if (val === "INTERCEPTED_AT_PREDICTED_ATM") {
      actualAtmInput.value = result.predicted_atm_id || "";
      actualAtmInput.disabled = false;
      actualAtmInput.placeholder = "Target ATM ID";
      feedbackBanner.style.background = "#ecfdf5";
      feedbackBanner.style.borderColor = "#a7f3d0";
      feedbackBanner.style.color = "#065f46";
      feedbackText.innerText = "Confirmed spatial hit on predicted ATM. Reinforces geospatial accuracy.";
    } else if (val === "INTERCEPTED_AT_OTHER_ATM") {
      if (actualAtmInput.value === result.predicted_atm_id) actualAtmInput.value = "";
      actualAtmInput.disabled = false;
      actualAtmInput.placeholder = "Enter Adjacent ATM ID (e.g. ATM_042)";
      feedbackBanner.style.background = "#eff6ff";
      feedbackBanner.style.borderColor = "#bfdbfe";
      feedbackBanner.style.color = "#1e40af";
      feedbackText.innerText = "Interception at adjacent ATM corridor. Spatial candidate cluster match.";
    } else if (val === "NO_CASHOUT") {
      actualAtmInput.value = "";
      actualAtmInput.disabled = true;
      actualAtmInput.placeholder = "N/A — No cashout detected";
      feedbackBanner.style.background = "#f8fafc";
      feedbackBanner.style.borderColor = "#e2e8f0";
      feedbackBanner.style.color = "#475569";
      feedbackText.innerText = "No cash-out attempt observed during target intervention window.";
    } else if (val === "FALSE_ALERT") {
      actualAtmInput.value = "";
      actualAtmInput.disabled = true;
      actualAtmInput.placeholder = "N/A — Benign activity";
      feedbackBanner.style.background = "#fff1f2";
      feedbackBanner.style.borderColor = "#fecdd3";
      feedbackBanner.style.color = "#9f1239";
      feedbackText.innerText = "Benign or non-fraudulent transaction profile. Flags priority calibration.";
    } else {
      actualAtmInput.value = "";
      actualAtmInput.disabled = true;
      actualAtmInput.placeholder = "N/A — Suspect evaded";
      feedbackBanner.style.background = "#f3f4f6";
      feedbackBanner.style.borderColor = "#e5e7eb";
      feedbackBanner.style.color = "#4b5563";
      feedbackText.innerText = "Suspect evaded perimeter before field unit arrival.";
    }
  }

  statusSelect.onchange = updateFeedbackBanner;
  updateFeedbackBanner();

  // Load dispatch info if available
  try {
    const disp = await API.getCaseDispatch(result.case_id);
    unitEl.innerText = disp ? `${disp.patrol_unit_assigned} (${disp.dispatch_status})` : "UNASSIGNED";
  } catch {
    unitEl.innerText = "UNASSIGNED";
  }

  // Load outcome metrics strip
  try {
    const metrics = await API.getOutcomeMetrics();
    const countEl = document.getElementById("kpiOutcomeCount");
    const hitsEl = document.getElementById("kpiOutcomeHits");
    const rateEl = document.getElementById("kpiOutcomeHitRate");
    if (countEl) countEl.innerText = metrics.total_outcomes_recorded;
    if (hitsEl) hitsEl.innerText = metrics.predicted_atm_match_count;
    if (rateEl) rateEl.innerText = `${metrics.prediction_hit_rate_pct}%`;
  } catch (err) {
    console.warn("Could not load outcome metrics:", err);
  }

  // Check if outcome already recorded / case resolved (view-only mode)
  const currentRole = getActiveRole();
  let isFinalized = result.case_status === "RESOLVED" || result.case_status === "CLOSED" || currentRole === "reporting";
  let existing = null;
  try {
    existing = await API.getCaseOutcome(result.case_id);
    if (existing) {
      statusSelect.value = existing.outcome_status;
      if (existing.actual_atm_id) actualAtmInput.value = existing.actual_atm_id;
      if (existing.notes) notesInput.value = existing.notes;
      isFinalized = true;
      updateFeedbackBanner();
    }
  } catch {}

  const formMode = document.getElementById("outcomeModalFormMode");
  const reportMode = document.getElementById("outcomeModalReportMode");
  const modalTitle = document.getElementById("outcomeModalTitle");

  if (isFinalized) {
    if (modalTitle) modalTitle.innerText = "Final Incident Resolution Record (Read-Only)";
    if (formMode) formMode.style.display = "none";
    if (reportMode) {
      reportMode.style.display = "block";
      const repBadge = document.getElementById("modalReportOutcomeBadge");
      const currentOut = existing || result._outcome;
      const modalOutDetails = getOutcomeDetails(currentOut, result.predicted_atm_id);
      if (repBadge && modalOutDetails) {
        repBadge.className = modalOutDetails.badgeClass;
        repBadge.innerText = "FINAL OUTCOME: " + modalOutDetails.badgeText;
      }
      const repCaseStatus = document.getElementById("modalReportCaseStatus");
      if (repCaseStatus) repCaseStatus.innerText = "CLOSED";
      const repHit = document.getElementById("modalReportSpatialHit");
      if (repHit && modalOutDetails) {
        repHit.innerText = modalOutDetails.spatialHitText;
      }
      const repPred = document.getElementById("modalReportPredictedAtm");
      if (repPred) repPred.innerText = result.predicted_atm_id || "--";
      const repAct = document.getElementById("modalReportActualAtm");
      if (repAct && modalOutDetails) {
        repAct.innerText = modalOutDetails.actualAtmText;
      }
      const repUnit = document.getElementById("modalReportUnit");
      if (repUnit) repUnit.innerText = result._dispatch?.patrol_unit_assigned || currentOut?.dispatch_id || "Patrol Unit";
      const repTime = document.getElementById("modalReportTimestamp");
      if (repTime) repTime.innerText = currentOut?.outcome_timestamp || "Resolved";
      const repNotes = document.getElementById("modalReportNotes");
      if (repNotes) repNotes.innerText = currentOut?.notes || "No remarks recorded.";
    }
    confirmBtn.style.display = "none";
  } else {
    if (modalTitle) modalTitle.innerText = "Record Incident Outcome & Interception Feedback";
    if (formMode) formMode.style.display = "block";
    if (reportMode) reportMode.style.display = "none";
    statusSelect.disabled = false;
    actualAtmInput.disabled = false;
    notesInput.disabled = false;
    confirmBtn.style.display = "inline-flex";
    confirmBtn.disabled = false;
    confirmBtn.innerText = "Record Outcome & Close";
  }

  modal.style.display = "flex";
}

function setupOutcomeModalListeners() {
  const modal = document.getElementById("outcomeModal");
  const closeBtn = document.getElementById("closeOutcomeModalBtn");
  const cancelBtn = document.getElementById("btnCancelOutcomeModal");
  const confirmBtn = document.getElementById("btnConfirmOutcomeModal");
  const statusSelect = document.getElementById("outcomeStatusSelect");
  const actualAtmInput = document.getElementById("outcomeActualAtmInput");
  const notesInput = document.getElementById("outcomeNotesInput");

  if (!modal) return;

  const closeModal = () => {
    modal.style.display = "none";
  };

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

  window.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.style.display === "flex") {
      closeModal();
    }
  });

  if (confirmBtn) {
    confirmBtn.addEventListener("click", async () => {
      const res = window.currentActivePrediction;
      if (!res || !res.case_id) return;

      const outcomeStatus = statusSelect.value;
      const actualAtm = actualAtmInput.value.trim() || null;
      const notes = notesInput.value.trim();

      confirmBtn.disabled = true;
      const origText = confirmBtn.innerText;
      confirmBtn.innerText = "Saving Outcome...";
      try {
        const out = await API.recordCaseOutcome(res.case_id, {
          outcome_status: outcomeStatus,
          actual_atm_id: actualAtm,
          notes: notes,
          auto_resolve_case: true,
        });
        res.case_status = "RESOLVED";
        res._outcome = out;
        closeModal();
        showToast(`Incident outcome recorded: ${out.outcome_status}. Case closed.`, "success");

        // Immediately update sequential operational state
        const caseStatusBadge = document.getElementById("predCaseStatusBadge");
        if (caseStatusBadge) {
          caseStatusBadge.innerText = "CASE STATUS: CLOSED";
          caseStatusBadge.className = "case-status-badge status-closed";
        }
        const outDetails = getOutcomeDetails(out, res.predicted_atm_id);
        const outcomeBadge = document.getElementById("predOutcomeBadge");
        if (outcomeBadge && outDetails) {
          outcomeBadge.style.display = "inline-flex";
          outcomeBadge.className = outDetails.badgeClass;
          outcomeBadge.innerText = "FINAL OUTCOME: " + outDetails.badgeText;
        }

        const btnTransition = document.getElementById("btnCaseTransition");
        if (btnTransition) btnTransition.style.display = "none";

        const btnRecordOutcome = document.getElementById("btnRecordOutcome");
        if (btnRecordOutcome) {
          btnRecordOutcome.style.display = "inline-flex";
          btnRecordOutcome.className = "btn-op-secondary";
          btnRecordOutcome.innerHTML = `<svg class="btn-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg><span>View Final Outcome</span>`;
          btnRecordOutcome.title = "View Final Recorded Outcome (Read-Only)";
        }
        const btnViewDispatch = document.getElementById("btnViewDispatch");
        if (btnViewDispatch) {
          btnViewDispatch.style.display = "inline-flex";
          btnViewDispatch.className = "btn-op-secondary";
          btnViewDispatch.title = "View Field Dispatch Details (Read-Only)";
        }

        const heroReportCard = document.getElementById("heroFinalOutcomeRecord");
        if (heroReportCard) {
          heroReportCard.style.display = "none";
        }

        // Render role-appropriate final resolution section replacing active playbook
        renderRolePlaybook(res, getActiveRole());

        await loadAlertHistory();
        loadInterventionPerformance();
        setWorkflowStep(7);
      } catch (err) {
        showToast(`Failed to record outcome: ${err.message}`, "error");
      } finally {
        confirmBtn.disabled = false;
        confirmBtn.innerText = origText;
      }
    });
  }
}

/**
 * Configure intervention performance toolbar listeners.
 */
function setupPerformanceListeners() {
  const refreshBtn = document.getElementById("btnRefreshPerformance");
  if (refreshBtn) refreshBtn.addEventListener("click", () => loadInterventionPerformance());
}

/**
 * Fetch and refresh intervention performance and operational analytics from backend API.
 */
async function loadInterventionPerformance() {
  const summaryEl = document.getElementById("perfStatusSummary");
  if (summaryEl) summaryEl.innerText = "Recalculating operational intervention performance from recorded cases and outcomes...";

  try {
    const data = await API.getInterventionPerformance();
    renderInterventionPerformance(data);
  } catch (err) {
    if (summaryEl) summaryEl.innerText = `Intervention analytics error: ${err.message}`;
  }
}

/**
 * Render intervention performance data to KPI cards and breakdown tables.
 */
function renderInterventionPerformance(data) {
  if (!data) return;

  const summaryEl = document.getElementById("perfStatusSummary");
  if (summaryEl) {
    summaryEl.innerText = `Operational metrics generated at ${data.generated_timestamp}. Analyzed ${data.total_actionable_cases} operational cases (${data.dispatched_cases} dispatched, ${data.resolved_cases} resolved) and ${data.total_outcomes_logged} verified outcomes.`;
  }

  // Pipeline Cards
  const totalCasesEl = document.getElementById("perfTotalCases");
  const newCasesEl = document.getElementById("perfNewCases");
  const dispCasesEl = document.getElementById("perfDispatchedCases");
  const resCasesEl = document.getElementById("perfResolvedCases");

  if (totalCasesEl) totalCasesEl.innerText = data.total_actionable_cases;
  if (newCasesEl) newCasesEl.innerText = data.new_alert_cases;
  if (dispCasesEl) dispCasesEl.innerText = data.dispatched_cases;
  if (resCasesEl) resCasesEl.innerText = data.resolved_cases;

  // Interception & Accuracy
  const hitRateEl = document.getElementById("perfSpatialHitRate");
  const matchedAtmsEl = document.getElementById("perfMatchedAtms");
  const interceptedEl = document.getElementById("perfInterceptedCases");
  const interceptRateEl = document.getElementById("perfInterceptionRate");

  if (hitRateEl) hitRateEl.innerText = `${data.spatial_hit_rate_pct}%`;
  if (matchedAtmsEl) matchedAtmsEl.innerText = data.predicted_vs_actual_matches;
  if (interceptedEl) interceptedEl.innerText = data.intercepted_cases;
  if (interceptRateEl) interceptRateEl.innerText = `${data.interception_success_rate_pct}%`;

  // Timing
  const t = data.timing || {};
  const alertToDispEl = document.getElementById("perfAlertToDispatch");
  const dispToOutEl = document.getElementById("perfDispatchToOutcome");
  const alertToOutEl = document.getElementById("perfAlertToOutcome");
  const timedCasesEl = document.getElementById("perfTimedCases");

  if (alertToDispEl) alertToDispEl.innerText = `${t.avg_alert_to_dispatch_mins}m`;
  if (dispToOutEl) dispToOutEl.innerText = `${t.avg_dispatch_to_outcome_mins}m`;
  if (alertToOutEl) alertToOutEl.innerText = `${t.avg_alert_to_outcome_mins}m`;
  if (timedCasesEl) timedCasesEl.innerText = t.sampled_timed_cases || 0;

  // Feedback Outcomes
  const totalOutcomesEl = document.getElementById("perfTotalOutcomes");
  const falseAlertsEl = document.getElementById("perfFalseAlerts");
  const noCashoutEl = document.getElementById("perfNoCashout");
  const unresolvedEl = document.getElementById("perfUnresolved");

  if (totalOutcomesEl) totalOutcomesEl.innerText = data.total_outcomes_logged;
  if (falseAlertsEl) falseAlertsEl.innerText = data.false_alert_count;
  if (noCashoutEl) noCashoutEl.innerText = data.no_cashout_count;
  if (unresolvedEl) unresolvedEl.innerText = data.unresolved_count;

  // Zone Breakdown Table
  const zoneTbody = document.getElementById("perfZoneTableBody");
  if (zoneTbody) {
    if (!data.performance_by_zone || data.performance_by_zone.length === 0) {
      zoneTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 12px;">No recorded operational cases across zones.</td></tr>`;
    } else {
      zoneTbody.innerHTML = data.performance_by_zone
        .map(z => `
          <tr>
            <td><b>${escapeHtml(z.zone_id.replace("ZONE_", ""))}</b></td>
            <td>${z.total_cases}</td>
            <td>${z.dispatched_cases}</td>
            <td>${z.resolved_cases}</td>
            <td>${z.outcomes_logged}</td>
            <td><b>${z.spatial_hits}</b></td>
            <td><span class="priority-tag ${z.spatial_hit_rate_pct > 0 ? "priority-low" : "priority-moderate"}">${z.spatial_hit_rate_pct}%</span></td>
          </tr>
        `)
        .join("");
    }
  }

  // ATM Breakdown Table
  const atmTbody = document.getElementById("perfAtmTableBody");
  if (atmTbody) {
    if (!data.performance_by_atm || data.performance_by_atm.length === 0) {
      atmTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 12px;">No recorded operational cases targeting ATMs.</td></tr>`;
    } else {
      atmTbody.innerHTML = data.performance_by_atm
        .map(a => `
          <tr>
            <td><b style="color: var(--accent-blue);">${escapeHtml(a.atm_id)}</b></td>
            <td>${escapeHtml(a.zone_id.replace("ZONE_", ""))}</td>
            <td>${a.total_cases}</td>
            <td>${a.dispatched_cases}</td>
            <td>${a.resolved_cases}</td>
            <td><b>${a.spatial_hits}</b></td>
            <td><span class="priority-tag ${a.spatial_hit_rate_pct > 0 ? "priority-low" : "priority-moderate"}">${a.spatial_hit_rate_pct}%</span></td>
          </tr>
        `)
        .join("");
    }
  }
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

/**
 * Switch operational workspace console mode (reporting vs investigator).
 */
let _citizenPollInterval = null;
let _investigatorPollInterval = null;
let _knownInvestigatorCaseIds = null;
let _currentCachedCases = [];

function stopAllPolling() {
  if (_citizenPollInterval) {
    clearInterval(_citizenPollInterval);
    _citizenPollInterval = null;
  }
  if (_investigatorPollInterval) {
    clearInterval(_investigatorPollInterval);
    _investigatorPollInterval = null;
  }
}

/**
 * Reviewed cases tracking in localStorage to preserve unread status across page refreshes.
 */
function getReviewedCases() {
  try {
    return new Set(JSON.parse(localStorage.getItem("investigator_reviewed_cases") || "[]"));
  } catch {
    return new Set();
  }
}

function markCaseReviewed(caseId) {
  if (!caseId) return;
  try {
    const set = getReviewedCases();
    if (!set.has(caseId)) {
      set.add(caseId);
      localStorage.setItem("investigator_reviewed_cases", JSON.stringify([...set]));
    }
    updateQueueDropdownUI();
  } catch (e) {
    console.warn("Could not save reviewed case:", e);
  }
}

/**
 * Updates the Investigator Case Queue dropdown options with [NEW] vs [REVIEWED] tags
 * and synchronizes the unread counter badge.
 */
function updateQueueDropdownUI() {
  const select = document.getElementById("investigatorCaseSelect");
  const countBadge = document.getElementById("queueNewCountBadge");
  if (!select) return;

  const reviewedSet = getReviewedCases();
  const currentVal = select.value;

  select.innerHTML = '<option value="">-- Select Incoming Case from Queue --</option>';

  let unreadCount = 0;
  if (_currentCachedCases && _currentCachedCases.length > 0) {
    _currentCachedCases.forEach((c) => {
      const isReviewed = reviewedSet.has(c.case_id);
      if (!isReviewed) unreadCount++;

      const opt = document.createElement("option");
      opt.value = c.case_id;
      const statusClean = (c.case_status || "NEW_ALERT").replace(/_/g, " ");
      const tag = isReviewed ? "[REVIEWED]" : "[NEW]";
      opt.textContent = `${tag} ${c.case_id} | ${statusClean} | Target: ${c.predicted_atm_id || "ATM"} (${c.priority_level || "MED"})`;
      if (!isReviewed) {
        opt.style.fontWeight = "bold";
      }
      if (c.case_id === currentVal) opt.selected = true;
      select.appendChild(opt);
    });
  } else {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No active cases in queue";
    select.appendChild(opt);
  }

  if (countBadge) {
    if (unreadCount > 0) {
      countBadge.innerText = `${unreadCount} NEW`;
      countBadge.style.display = "inline-flex";
    } else {
      countBadge.style.display = "none";
    }
  }
}

/**
 * Displays a professional, non-blocking notification when an actual new case is reported.
 */
function showNewCaseNotification(data) {
  let container = document.getElementById("liveCaseNotificationContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "liveCaseNotificationContainer";
    container.className = "live-notification-container";
    document.body.appendChild(container);
  }

  const notif = document.createElement("div");
  notif.className = "new-case-notification-card";
  notif.setAttribute("role", "alert");

  const pLevel = (data.priorityLevel || "MEDIUM").toUpperCase();
  const pClass = pLevel === "CRITICAL" ? "priority-critical" : (pLevel === "HIGH" ? "priority-high" : "priority-moderate");

  notif.innerHTML = `
    <div class="notif-header">
      <div class="notif-title-group">
        <svg class="notif-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span class="notif-title">New Case Reported</span>
      </div>
      <button type="button" class="notif-close-btn" aria-label="Dismiss Notification">&times;</button>
    </div>
    <div class="notif-body">
      <div class="notif-row">
        <span class="notif-case-id font-mono">${escapeHtml(data.caseId)}</span>
        <span class="priority-tag ${pClass}">${pLevel}</span>
      </div>
      <div class="notif-detail">
        Target: <b style="color: var(--accent-blue);">${escapeHtml(data.targetAtm)}</b> &bull; ${escapeHtml(data.zone)}
      </div>
    </div>
    <div class="notif-footer">
      <button type="button" class="notif-action-btn">Inspect &amp; Triage Case &rarr;</button>
    </div>
  `;

  const actionBtn = notif.querySelector(".notif-action-btn");
  if (actionBtn) {
    actionBtn.onclick = () => {
      markCaseReviewed(data.caseId);
      loadCaseById(data.caseId);
      notif.remove();
    };
  }

  const closeBtn = notif.querySelector(".notif-close-btn");
  if (closeBtn) {
    closeBtn.onclick = () => notif.remove();
  }

  container.appendChild(notif);

  setTimeout(() => {
    if (notif.parentNode) {
      notif.style.opacity = "0";
      notif.style.transform = "translateX(20px)";
      notif.style.transition = "all 0.3s ease-out";
      setTimeout(() => notif.remove(), 300);
    }
  }, 8000);
}

/**
 * Live polling for Investigator Console to detect newly reported cases and state changes.
 */
function startInvestigatorPolling() {
  if (_investigatorPollInterval) clearInterval(_investigatorPollInterval);
  _investigatorPollInterval = setInterval(async () => {
    if (getActiveRole() !== "investigator") return;
    try {
      await loadInvestigatorQueue();
      if (window.currentActivePrediction?.case_id) {
        const c = await API.getCase(window.currentActivePrediction.case_id);
        if (c && c.case_status !== window.currentActivePrediction.case_status) {
          await loadCaseById(c.case_id);
        }
      }
    } catch (err) {
      console.warn("Investigator polling check:", err);
    }
  }, 3000);
}

/**
 * Live polling for Citizen Console to receive real-time dispatch and outcome updates.
 */
function startCitizenPolling(caseId) {
  if (!caseId) return;
  if (_citizenPollInterval) clearInterval(_citizenPollInterval);
  _citizenPollInterval = setInterval(async () => {
    if (getActiveRole() !== "reporting") return;
    try {
      const c = await API.getCase(caseId);
      if (!c) return;

      let disp = null;
      let out = null;
      try { disp = await API.getCaseDispatch(caseId); } catch {}
      try { out = await API.getCaseOutcome(caseId); } catch {}

      if (window.currentActivePrediction && window.currentActivePrediction.case_id === caseId) {
        window.currentActivePrediction.case_status = c.case_status;
        window.currentActivePrediction._dispatch = disp;
        window.currentActivePrediction._outcome = out;
        if (window._currentUpdateCaseControls) {
          window._currentUpdateCaseControls(caseId, c.case_status, disp, out);
        }
      } else {
        await loadCitizenCase(caseId);
      }

      if (c.case_status === "RESOLVED" || c.case_status === "CLOSED") {
        clearInterval(_citizenPollInterval);
        _citizenPollInterval = null;
      }
    } catch (err) {
      console.warn("Citizen polling check:", err);
    }
  }, 2500);
}

/**
 * Loads and renders a citizen's active reported case.
 */
async function loadCitizenCase(caseId) {
  if (!caseId) return;
  try {
    const c = await API.getCase(caseId);
    if (!c) return;

    let disp = null;
    let out = null;
    try { disp = await API.getCaseDispatch(caseId); } catch {}
    try { out = await API.getCaseOutcome(caseId); } catch {}

    const predObj = {
      case_id: c.case_id,
      case_status: c.case_status,
      predicted_atm_id: c.predicted_atm_id,
      predicted_zone_id: c.predicted_zone_id,
      priority_score: c.priority_score,
      priority_level: c.priority_level || "MEDIUM",
      confidence_score: c.confidence_score || 0.15,
      predicted_window_start: c.created_timestamp,
      predicted_window_end: "",
      predicted_lead_time_mins: 20,
      risk_level: c.priority_level === "CRITICAL" ? "CRITICAL" : (c.priority_level === "HIGH" ? "ELEVATED" : "MODERATE"),
      top_candidates: c.top_candidates || [],
      explanation_codes: c.explanation_codes || [],
      priority_reasons: c.priority_reasons || [],
      _dispatch: disp,
      _outcome: out,
    };

    renderPredictionResult(predObj);
    MapController.highlightPrediction(predObj.predicted_atm_id, predObj.top_candidates);
  } catch (err) {
    console.warn("Could not load citizen case:", err);
  }
}

/**
 * Switch operational workspace console mode (reporting vs investigator).
 */
export async function applyConsoleMode(role) {
  setActiveRole(role);
  stopAllPolling();

  const btnReporting = document.getElementById("btnRoleReporting");
  const btnInvestigator = document.getElementById("btnRoleInvestigator");
  const headerRoleBadge = document.getElementById("headerRoleBadge");
  const intakeSection = document.getElementById("intakeFormSection");
  const queueSection = document.getElementById("investigatorQueueSection");
  const citizenNotice = document.getElementById("citizenTrackingNotice");
  const forecastCard = document.getElementById("forecastCard");
  const placeholderCard = document.getElementById("forecastCardPlaceholder");
  const placeholderTitle = document.getElementById("forecastPlaceholderTitle");
  const placeholderText = document.getElementById("forecastPlaceholderText");

  // Tab buttons for investigator-only intel
  const tabClusters = document.querySelector('.tab-btn[data-tab="tab-clusters"]');
  const tabConvergences = document.querySelector('.tab-btn[data-tab="tab-convergences"]');
  const tabPerformance = document.querySelector('.tab-btn[data-tab="tab-performance"]');

  // Operational action buttons in the hero toolbar
  const btnTransition = document.getElementById("btnCaseTransition");
  const btnRecordOutcome = document.getElementById("btnRecordOutcome");
  const btnViewDispatch = document.getElementById("btnViewDispatch");
  const btnExportEvidence = document.getElementById("btnExportEvidence");

  if (role === "investigator") {
    if (btnReporting) btnReporting.classList.remove("active");
    if (btnInvestigator) btnInvestigator.classList.add("active");
    if (headerRoleBadge) headerRoleBadge.innerText = "Investigator Ops Mode";

    if (queueSection) queueSection.style.display = "block";
    // Investigator never sees complaint intake or Run Predictive Forecast button
    if (intakeSection) intakeSection.style.display = "none";

    if (citizenNotice) citizenNotice.style.display = "none";

    // Show investigator tabs
    if (tabClusters) tabClusters.style.display = "inline-flex";
    if (tabConvergences) tabConvergences.style.display = "inline-flex";
    if (tabPerformance) tabPerformance.style.display = "inline-flex";

    // If no case is loaded in the workbench, display investigator placeholder
    if (!window.currentActivePrediction) {
      if (placeholderCard) placeholderCard.style.display = "flex";
      if (forecastCard) forecastCard.style.display = "none";
      if (placeholderTitle) placeholderTitle.innerText = "Awaiting Operational Case Selection";
      if (placeholderText) {
        placeholderText.innerText = "Select an incoming incident from the operational queue above to inspect predictive evidence, coordinate field patrol routing, and log verified outcomes.";
      }
    } else {
      if (placeholderCard) placeholderCard.style.display = "none";
      if (forecastCard) forecastCard.style.display = "block";
    }

    // Populate queue and start live polling for incoming citizen reports
    await loadInvestigatorQueue();
    startInvestigatorPolling();
  } else {
    // Case Reporting / Citizen Console
    if (btnReporting) btnReporting.classList.add("active");
    if (btnInvestigator) btnInvestigator.classList.remove("active");
    if (headerRoleBadge) headerRoleBadge.innerText = "Citizen Reporting Mode";

    if (queueSection) queueSection.style.display = "none";
    // Citizen enters complaint/case details
    if (intakeSection) intakeSection.style.display = "block";
    const intakeTitle = document.getElementById("intakeHeadingTitle");
    if (intakeTitle) intakeTitle.innerText = "Predictive Incident Triage";

    // Hide operational investigator buttons
    if (btnTransition) btnTransition.style.display = "none";
    if (btnRecordOutcome) btnRecordOutcome.style.display = "none";
    if (btnViewDispatch) btnViewDispatch.style.display = "none";
    if (btnExportEvidence) btnExportEvidence.style.display = "none";

    // Hide investigator-only intel tabs
    if (tabClusters) tabClusters.style.display = "none";
    if (tabConvergences) tabConvergences.style.display = "none";
    if (tabPerformance) tabPerformance.style.display = "none";

    // If an investigator-only tab was currently active, switch back to tab-analytics
    const activeTabBtn = document.querySelector(".tab-btn.active");
    if (activeTabBtn && ["tab-clusters", "tab-convergences", "tab-performance"].includes(activeTabBtn.getAttribute("data-tab"))) {
      const defaultTabBtn = document.querySelector('.tab-btn[data-tab="tab-analytics"]');
      if (defaultTabBtn) defaultTabBtn.click();
    }

    // Citizen tracks their own case
    const savedCitizenCaseId = sessionStorage.getItem("citizen_active_case_id");
    if (window.currentActivePrediction && window.currentActivePrediction.case_id === savedCitizenCaseId) {
      if (placeholderCard) placeholderCard.style.display = "none";
      if (forecastCard) forecastCard.style.display = "block";
      startCitizenPolling(savedCitizenCaseId);
    } else if (savedCitizenCaseId) {
      await loadCitizenCase(savedCitizenCaseId);
      startCitizenPolling(savedCitizenCaseId);
    } else {
      if (placeholderCard) placeholderCard.style.display = "flex";
      if (forecastCard) forecastCard.style.display = "none";
      if (placeholderTitle) placeholderTitle.innerText = "Awaiting Incident Complaint Intake";
      if (placeholderText) {
        placeholderText.innerText = "Select an operational scenario preset above or submit complaint parameters to trigger calibrated spatial forecasting, tactical triage, and field patrol routing.";
      }
    }
  }

  // Update controls, playbook, and hero directive for active prediction
  if (window.currentActivePrediction) {
    renderRolePlaybook(window.currentActivePrediction, role);
    const heroActionEl = document.getElementById("heroActionDirective");
    if (heroActionEl) {
      const pred = window.currentActivePrediction;
      const isClosed = (pred.case_status === "RESOLVED" || pred.case_status === "CLOSED");
      if (isClosed) {
        heroActionEl.innerText = (role === "reporting")
          ? "Case resolution finalized by law enforcement. View official case outcome details below."
          : "Operational response concluded. Outcome recorded and case closed. Review resolution audit report below.";
      } else if (role === "reporting") {
        heroActionEl.innerText = "Citizen Guidance: Protect yourself & secure your account. Contact your bank immediately to freeze compromised cards/accounts and preserve evidence.";
      } else {
        const predAtm = pred.predicted_atm_id || "target ATM";
        const winStr = (pred.predicted_window_start && pred.predicted_window_end)
          ? `${pred.predicted_window_start.substring(11, 16)} - ${pred.predicted_window_end.substring(11, 16)} hrs`
          : "operational window";
        heroActionEl.innerText = `Tactical Directive: Respond, intervene & verify outcome. Dispatch field patrol to secure ${predAtm} within ${winStr}.`;
      }
    }
    if (window._currentUpdateCaseControls) {
      window._currentUpdateCaseControls(
        window.currentActivePrediction.case_id,
        window.currentActivePrediction.case_status,
        window.currentActivePrediction._dispatch,
        window.currentActivePrediction._outcome
      );
    }
  }
}

/**
 * Loads recent operational cases into the queue select dropdown and triggers new-case notifications.
 */
async function loadInvestigatorQueue() {
  const select = document.getElementById("investigatorCaseSelect");
  if (!select) return;
  try {
    const cases = await API.getCases({ limit: 30 });
    _currentCachedCases = cases || [];

    if (_knownInvestigatorCaseIds === null) {
      // First queue initialization: track existing cases without firing notifications
      _knownInvestigatorCaseIds = new Set((cases || []).map(c => c.case_id));
    } else {
      // Shared DB polling check: detect newly arrived cases reported by citizen console
      const newArrivals = (cases || []).filter(c => !_knownInvestigatorCaseIds.has(c.case_id));
      if (newArrivals.length > 0) {
        newArrivals.forEach(c => {
          _knownInvestigatorCaseIds.add(c.case_id);
          showNewCaseNotification({
            caseId: c.case_id,
            priorityLevel: c.priority_level || "MEDIUM",
            targetAtm: c.predicted_atm_id || "ATM",
            zone: (c.predicted_zone_id || "").replace("ZONE_", "Zone "),
          });
        });
      }
    }

    updateQueueDropdownUI();
  } catch (err) {
    console.warn("Could not load case queue:", err);
  }
}

/**
 * Loads an operational case from backend evidence into the active workbench.
 */
async function loadCaseById(caseId) {
  if (!caseId) return;
  try {
    markCaseReviewed(caseId);
    showToast(`Loading operational case ${caseId}...`, "info");
    const evidence = await API.getEvidence(caseId);
    if (!evidence || !evidence.case) {
      showToast(`Case ${caseId} not found or has no evidence packet.`, "error");
      return;
    }

    const c = evidence.case;
    const pred = evidence.prediction || {};
    const topCandidates = (evidence.top_candidates && evidence.top_candidates.length > 0)
      ? evidence.top_candidates
      : (pred.top_candidates || []);

    const predObj = {
      ...pred,
      case_id: c.case_id,
      case_status: c.case_status,
      predicted_atm_id: c.predicted_atm_id || pred.predicted_atm_id,
      predicted_zone_id: c.predicted_zone_id || pred.predicted_zone_id,
      priority_score: c.priority_score ?? pred.priority_score ?? 50,
      priority_level: c.priority_level || pred.priority_level || "MEDIUM",
      confidence_score: pred.confidence_score ?? 0.15,
      predicted_window_start: pred.predicted_window_start || c.created_timestamp,
      predicted_window_end: pred.predicted_window_end || "",
      predicted_lead_time_mins: pred.predicted_lead_time_mins || 20,
      risk_level: pred.risk_level || "MODERATE",
      top_candidates: topCandidates,
      explanation_codes: pred.explanation_codes || [],
      priority_reasons: pred.priority_reasons || [],
      playbook: pred.playbook || {
        tactical_disposition: "TACTICAL INTERCEPTION",
        dispatch_brief: evidence.dispatch?.tactical_brief || `[TACTICAL BRIEF] Target ATM: ${c.predicted_atm_id}`,
        recommended_actions: evidence.dispatch?.playbook_actions || []
      },
      _dispatch: evidence.dispatch || null,
      _outcome: null,
    };

    try {
      predObj._outcome = await API.getCaseOutcome(caseId);
    } catch {}

    if (!predObj._dispatch) {
      try {
        predObj._dispatch = await API.getCaseDispatch(caseId);
      } catch {}
    }

    renderPredictionResult(predObj);
    MapController.highlightPrediction(predObj.predicted_atm_id, predObj.top_candidates);
    showToast(`Loaded operational case ${caseId} (${predObj.case_status})`, "success");
  } catch (err) {
    showToast(`Failed to load case ${caseId}: ${err.message}`, "error");
  }
}

/**
 * Setup console switcher tabs and queue listener events.
 */
function setupConsoleSwitcher() {
  const btnReporting = document.getElementById("btnRoleReporting");
  const btnInvestigator = document.getElementById("btnRoleInvestigator");

  if (btnReporting) {
    btnReporting.addEventListener("click", () => {
      applyConsoleMode("reporting");
      showToast("Switched to Case Reporting / Citizen Console", "info");
    });
  }

  if (btnInvestigator) {
    btnInvestigator.addEventListener("click", () => {
      applyConsoleMode("investigator");
      showToast("Switched to Investigator / Operations Console", "info");
    });
  }

  // Setup queue controls
  const select = document.getElementById("investigatorCaseSelect");
  if (select) {
    select.addEventListener("change", (e) => {
      const cid = e.target.value;
      if (cid) {
        markCaseReviewed(cid);
        loadCaseById(cid);
      }
    });
  }

  const btnManual = document.getElementById("btnManualLoadCase");
  const inputManual = document.getElementById("manualCaseIdInput");
  if (btnManual && inputManual) {
    btnManual.addEventListener("click", () => {
      const cid = inputManual.value.trim();
      if (cid) {
        markCaseReviewed(cid);
        loadCaseById(cid);
      } else {
        showToast("Please enter a valid Case ID", "warning");
      }
    });
    inputManual.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const cid = inputManual.value.trim();
        if (cid) {
          markCaseReviewed(cid);
          loadCaseById(cid);
        }
      }
    });
  }

  const btnRefreshQueue = document.getElementById("btnRefreshCaseQueue");
  if (btnRefreshQueue) {
    btnRefreshQueue.addEventListener("click", async () => {
      await loadInvestigatorQueue();
      showToast("Operational case queue refreshed", "info");
    });
  }
}

