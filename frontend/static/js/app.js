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
  setupPerformanceListeners();

  // Initialize Workflow Ribbon to Step 1: Complaint Intake
  setWorkflowStep(1);

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
    const currentDisp = dispatchInfo || result._dispatch || null;
    const currentOut = outcomeInfo || result._outcome || null;

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

    if (outcomeBadge) {
      if (!caseId || !currentOut) {
        outcomeBadge.style.display = "none";
      } else {
        const st = currentOut.outcome_status;
        let badgeClass = "outcome-badge";
        let label = (status === "RESOLVED" || status === "CLOSED") ? "FINAL OUTCOME: " : "OUTCOME: ";
        if (currentOut.is_spatial_hit || st === "INTERCEPTED_AT_PREDICTED_ATM") {
          badgeClass += " outcome-hit";
          label += "INTERCEPTED AT PREDICTED ATM";
        } else if (st === "INTERCEPTED_AT_OTHER_ATM") {
          badgeClass += " outcome-other";
          label += "INTERCEPTED AT OTHER ATM";
        } else if (st === "FALSE_ALERT") {
          badgeClass += " outcome-false";
          label += "FALSE ALERT";
        } else if (st === "NO_CASHOUT") {
          badgeClass += " outcome-false";
          label += "NO CASHOUT";
        } else {
          badgeClass += " outcome-unresolved";
          label += "UNRESOLVED — SUSPECT EVADED";
        }
        outcomeBadge.className = badgeClass;
        outcomeBadge.innerText = label;
        outcomeBadge.style.display = "inline-flex";
      }
    }

    // Sequential Operational State Machine Controls
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

    // Final Resolution Report Card in Hero
    const heroReportCard = document.getElementById("heroFinalOutcomeRecord");
    if (heroReportCard) {
      if (status === "RESOLVED" || status === "CLOSED") {
        heroReportCard.style.display = "block";
        const repBadge = document.getElementById("reportOutcomeBadge");
        if (repBadge && outcomeBadge) {
          repBadge.className = outcomeBadge.className;
          repBadge.innerText = outcomeBadge.innerText;
        }
        const repCaseStatus = document.getElementById("reportCaseStatus");
        if (repCaseStatus) repCaseStatus.innerText = "CLOSED";
        const repSpatialHit = document.getElementById("reportSpatialHit");
        if (repSpatialHit) {
          repSpatialHit.innerText = (currentOut?.is_spatial_hit || currentOut?.outcome_status === "INTERCEPTED_AT_PREDICTED_ATM") 
            ? "Confirmed Spatial Hit" 
            : "Adjacent / Non-Target Resolution";
        }
        const repPredAtm = document.getElementById("reportPredictedAtm");
        if (repPredAtm) repPredAtm.innerText = result.predicted_atm_id || "--";
        const repActualAtm = document.getElementById("reportActualAtm");
        if (repActualAtm) repActualAtm.innerText = currentOut?.actual_atm_id || result.predicted_atm_id || "--";
        const repUnit = document.getElementById("reportUnit");
        if (repUnit) repUnit.innerText = currentDisp?.patrol_unit_assigned || "PCR Unit";
        const repTime = document.getElementById("reportTimestamp");
        if (repTime) repTime.innerText = currentOut?.outcome_timestamp || new Date().toISOString().replace("T", " ").substring(0, 19);
        const repNotes = document.getElementById("reportNotes");
        if (repNotes) repNotes.innerText = currentOut?.notes || "No debrief remarks recorded.";
      } else {
        heroReportCard.style.display = "none";
      }
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
          const iconSvg = document.getElementById("copyBriefIconSvg");
          const text = document.getElementById("copyBriefText");
          if (iconSvg) iconSvg.innerHTML = `<polyline points="20 6 9 17 4 12"/>`;
          if (text) text.innerText = "Copied!";
          copyBtn.classList.add("copied");
          showToast("Tactical Dispatch Brief copied to clipboard!", "success");
          setTimeout(() => {
            if (iconSvg) iconSvg.innerHTML = `<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>`;
            if (text) text.innerText = "Copy Brief";
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
      feedbackBanner.style.background = "#ecfdf5";
      feedbackBanner.style.borderColor = "#a7f3d0";
      feedbackBanner.style.color = "#065f46";
      feedbackText.innerText = "Confirmed spatial hit on predicted ATM. Reinforces geospatial accuracy.";
    } else if (val === "INTERCEPTED_AT_OTHER_ATM") {
      feedbackBanner.style.background = "#eff6ff";
      feedbackBanner.style.borderColor = "#bfdbfe";
      feedbackBanner.style.color = "#1e40af";
      feedbackText.innerText = "Interception at adjacent ATM corridor. Spatial candidate cluster match.";
    } else if (val === "NO_CASHOUT") {
      feedbackBanner.style.background = "#f8fafc";
      feedbackBanner.style.borderColor = "#e2e8f0";
      feedbackBanner.style.color = "#475569";
      feedbackText.innerText = "No cash-out attempt observed during target intervention window.";
    } else if (val === "FALSE_ALERT") {
      feedbackBanner.style.background = "#fff1f2";
      feedbackBanner.style.borderColor = "#fecdd3";
      feedbackBanner.style.color = "#9f1239";
      feedbackText.innerText = "Benign or non-fraudulent transaction profile. Flags priority calibration.";
    } else {
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
  let isFinalized = result.case_status === "RESOLVED";
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
      if (repBadge && currentOut) {
        const st = currentOut.outcome_status;
        let bCls = "outcome-badge";
        let bTxt = "FINAL OUTCOME: ";
        if (currentOut.is_spatial_hit || st === "INTERCEPTED_AT_PREDICTED_ATM") {
          bCls += " outcome-hit";
          bTxt += "INTERCEPTED AT PREDICTED ATM";
        } else if (st === "INTERCEPTED_AT_OTHER_ATM") {
          bCls += " outcome-other";
          bTxt += "INTERCEPTED AT OTHER ATM";
        } else if (st === "FALSE_ALERT") {
          bCls += " outcome-false";
          bTxt += "FALSE ALERT";
        } else if (st === "NO_CASHOUT") {
          bCls += " outcome-false";
          bTxt += "NO CASHOUT";
        } else {
          bCls += " outcome-unresolved";
          bTxt += "UNRESOLVED — SUSPECT EVADED";
        }
        repBadge.className = bCls;
        repBadge.innerText = bTxt;
      }
      const repCaseStatus = document.getElementById("modalReportCaseStatus");
      if (repCaseStatus) repCaseStatus.innerText = "CLOSED";
      const repHit = document.getElementById("modalReportSpatialHit");
      if (repHit) {
        repHit.innerText = (currentOut?.is_spatial_hit || currentOut?.outcome_status === "INTERCEPTED_AT_PREDICTED_ATM")
          ? "Confirmed Spatial Hit"
          : "Adjacent / Non-Target Resolution";
      }
      const repPred = document.getElementById("modalReportPredictedAtm");
      if (repPred) repPred.innerText = result.predicted_atm_id || "--";
      const repAct = document.getElementById("modalReportActualAtm");
      if (repAct) repAct.innerText = currentOut?.actual_atm_id || result.predicted_atm_id || "--";
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
        const outcomeBadge = document.getElementById("predOutcomeBadge");
        if (outcomeBadge) {
          outcomeBadge.style.display = "inline-flex";
          let badgeClass = "outcome-badge";
          let label = "FINAL OUTCOME: ";
          if (out.is_spatial_hit || out.outcome_status === "INTERCEPTED_AT_PREDICTED_ATM") {
            badgeClass += " outcome-hit";
            label += "INTERCEPTED AT PREDICTED ATM";
          } else if (out.outcome_status === "INTERCEPTED_AT_OTHER_ATM") {
            badgeClass += " outcome-other";
            label += "INTERCEPTED AT OTHER ATM";
          } else if (out.outcome_status === "FALSE_ALERT") {
            badgeClass += " outcome-false";
            label += "FALSE ALERT";
          } else if (out.outcome_status === "NO_CASHOUT") {
            badgeClass += " outcome-false";
            label += "NO CASHOUT";
          } else {
            badgeClass += " outcome-unresolved";
            label += "UNRESOLVED — SUSPECT EVADED";
          }
          outcomeBadge.className = badgeClass;
          outcomeBadge.innerText = label;
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
          heroReportCard.style.display = "block";
          const repBadge = document.getElementById("reportOutcomeBadge");
          if (repBadge && outcomeBadge) {
            repBadge.className = outcomeBadge.className;
            repBadge.innerText = outcomeBadge.innerText;
          }
          const repCaseStatus = document.getElementById("reportCaseStatus");
          if (repCaseStatus) repCaseStatus.innerText = "RESOLVED / CLOSED";
          const repSpatialHit = document.getElementById("reportSpatialHit");
          if (repSpatialHit) {
            repSpatialHit.innerText = (out.is_spatial_hit || out.outcome_status === "INTERCEPTED_AT_PREDICTED_ATM") 
              ? "Confirmed Spatial Hit" 
              : "Adjacent / Non-Target Resolution";
          }
          const repPredAtm = document.getElementById("reportPredictedAtm");
          if (repPredAtm) repPredAtm.innerText = res.predicted_atm_id || "--";
          const repActualAtm = document.getElementById("reportActualAtm");
          if (repActualAtm) repActualAtm.innerText = out.actual_atm_id || res.predicted_atm_id || "--";
          const repUnit = document.getElementById("reportUnit");
          if (repUnit) repUnit.innerText = res._dispatch?.patrol_unit_assigned || "PCR Unit";
          const repTime = document.getElementById("reportTimestamp");
          if (repTime) repTime.innerText = out.outcome_timestamp || new Date().toISOString().replace("T", " ").substring(0, 19);
          const repNotes = document.getElementById("reportNotes");
          if (repNotes) repNotes.innerText = out.notes || "No debrief remarks recorded.";
        }

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

