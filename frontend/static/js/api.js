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
      const msg = errorData.detail || `Request failed with status ${response.status}`;
      throw new Error(msg);
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
};

