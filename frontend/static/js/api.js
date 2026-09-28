/**
 * API Client Layer for Cybercrime Predictive Analytics Framework.
 * Interfaces with the FastAPI backend REST endpoints.
 */

const API_BASE = "/api";

async function request(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        "Content-Type": "application/json",
      },
      ...options,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      let msg = errorData.detail;
      if (typeof msg !== "string") {
        if (Array.isArray(errorData.errors)) {
          msg = errorData.errors.map(e => `${e.loc ? e.loc.slice(-1)[0] : "field"}: ${e.msg}`).join("; ");
        } else {
          msg = `Request failed with status ${response.status}`;
        }
      }
      const err = new Error(msg);
      err.status = response.status;
      err.errorData = errorData;
      err.fieldErrors = errorData.field_errors || {};
      throw err;
    }

    return await response.json();
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

export const API = {
  // 1. Executive Dashboard KPIs
  async getStats() {
    return await request("/stats");
  },

  // 2. Monitored ATM Network
  async getATMs() {
    return await request("/atms");
  },

  // 3. Hotspot Aggregates
  async getHotspots() {
    return await request("/hotspots");
  },

  // 4. Paginated Complaints Query
  async getComplaints(limit = 25, offset = 0, category = null, zone = null) {
    let url = `/complaints?limit=${limit}&offset=${offset}`;
    if (category) url += `&category=${encodeURIComponent(category)}`;
    if (zone) url += `&zone=${encodeURIComponent(zone)}`;
    return await request(url);
  },

  // 5. Real-Time Predictive Inference
  async predict(complaintPayload) {
    return await request("/predict", {
      method: "POST",
      body: JSON.stringify(complaintPayload),
    });
  },

  // 6. Actionable Alerts History
  async getPredictions(limit = 20) {
    return await request(`/predictions?limit=${limit}`);
  },

  // 7. Model Provenance & Verified Phase 2 Metrics
  async getModelInfo() {
    return await request("/model-info");
  },

  // 8. Emerging Cash-Out Clusters (Feature 1)
  async getClusters(params = {}) {
    const q = new URLSearchParams();
    if (params.window_hours) q.append("window_hours", params.window_hours);
    if (params.min_events) q.append("min_events", params.min_events);
    if (params.zone) q.append("zone", params.zone);
    if (params.source) q.append("source", params.source);
    if (params.reference_timestamp) q.append("reference_timestamp", params.reference_timestamp);
    const qs = q.toString();
    return await request(`/analytics/clusters${qs ? `?${qs}` : ""}`);
  },

  // 9. Repeated ATM / Zone Convergence Detection (Feature 2)
  async getConvergences(params = {}) {
    const q = new URLSearchParams();
    if (params.window_hours) q.append("window_hours", params.window_hours);
    if (params.min_matches) q.append("min_matches", params.min_matches);
    if (params.target_type) q.append("target_type", params.target_type);
    if (params.zone) q.append("zone", params.zone);
    if (params.reference_timestamp) q.append("reference_timestamp", params.reference_timestamp);
    const qs = q.toString();
    return await request(`/analytics/convergences${qs ? `?${qs}` : ""}`);
  },

  // 10. Operational Case Lifecycle Management
  async getCases(params = {}) {
    const q = new URLSearchParams();
    if (params.status) q.append("status", params.status);
    if (params.limit) q.append("limit", params.limit);
    const qs = q.toString();
    return await request(`/cases${qs ? `?${qs}` : ""}`);
  },

  async getCase(caseId) {
    return await request(`/cases/${encodeURIComponent(caseId)}`);
  },

  async updateCaseStatus(caseId, status, notes = "") {
    return await request(`/cases/${encodeURIComponent(caseId)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, notes }),
    });
  },

  // 11. Field Patrol Dispatch Routing & Evidence Export (Feature)
  async dispatchPatrol(caseId, payload = {}) {
    return await request(`/cases/${encodeURIComponent(caseId)}/dispatch`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getCaseDispatch(caseId) {
    return await request(`/cases/${encodeURIComponent(caseId)}/dispatch`);
  },

  async getDispatches(limit = 25) {
    return await request(`/dispatches?limit=${limit}`);
  },

  getEvidenceDownloadUrl(caseId, format = "json") {
    return `${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence?format=${encodeURIComponent(format)}&download=true`;
  },

  async getEvidence(caseId, format = "json") {
    return await request(`/cases/${encodeURIComponent(caseId)}/evidence?format=${encodeURIComponent(format)}`);
  },

  // 12. Incident Outcome Logging & Interception Feedback Loop (Feature)
  async recordCaseOutcome(caseId, payload = {}) {
    return await request(`/cases/${encodeURIComponent(caseId)}/outcome`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getCaseOutcome(caseId) {
    return await request(`/cases/${encodeURIComponent(caseId)}/outcome`);
  },

  async getOutcomes(limit = 25) {
    return await request(`/outcomes?limit=${limit}`);
  },

  async getOutcomeMetrics() {
    return await request("/outcomes/metrics");
  },

  // 13. Intervention Performance & Operational Analytics (Feature)
  async getInterventionPerformance() {
    return await request("/analytics/intervention-performance");
  },
};



