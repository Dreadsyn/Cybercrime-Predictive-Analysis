/**
 * Geospatial Map Controller using Leaflet.js.
 * Displays ATM locations, administrative zones, interactive selection telemetry,
 * and real-time prediction tactical overlays in a clean, professional light theme.
 */

let mapInstance = null;
let atmMarkers = {};
let targetHighlightLayer = null;
let zonePolygons = [];
let currentZoneFilter = "ALL";
let currentlySelectedAtmId = null;

const ZONE_CENTERS = {
  ZONE_CENTRAL: { lat: 28.6300, lon: 77.2200, name: "Central Commercial Core", color: "#0284c7" },
  ZONE_NORTH:   { lat: 28.7000, lon: 77.1500, name: "North Transport Nexus", color: "#0d9488" },
  ZONE_SOUTH:   { lat: 28.5300, lon: 77.2000, name: "South Institutional Hub", color: "#8b5cf6" },
  ZONE_EAST:    { lat: 28.6200, lon: 77.2900, name: "East Industrial Fringe", color: "#ea580c" },
  ZONE_WEST:    { lat: 28.6500, lon: 77.1000, name: "West Market Corridor", color: "#16a34a" },
};

export const MapController = {
  init(containerId = "map") {
    if (mapInstance) return mapInstance;

    // Center on Metropolitan Operational Coordinates
    mapInstance = L.map(containerId, {
      center: [28.6300, 77.2000],
      zoom: 11,
      minZoom: 10,
      maxZoom: 18,
      zoomControl: true,
    });

    // Standard OpenStreetMap key-free light tile provider (clean, familiar, Google-Maps style)
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(mapInstance);

    this.renderZones();
    this.setupPanelListeners();
    return mapInstance;
  },

  renderZones() {
    zonePolygons.forEach(p => mapInstance.removeLayer(p));
    zonePolygons = [];

    Object.entries(ZONE_CENTERS).forEach(([zoneId, z]) => {
      const circle = L.circle([z.lat, z.lon], {
        radius: 3500,
        color: z.color,
        fillColor: z.color,
        fillOpacity: 0.05,
        weight: 1.5,
        dashArray: "4, 6",
      }).addTo(mapInstance);

      circle.bindTooltip(`<b>${zoneId.replace("ZONE_", "Zone ")}</b><br><small>${z.name}</small>`, {
        permanent: false,
        direction: "center",
        className: "zone-tooltip",
      });

      zonePolygons.push(circle);
    });
  },

  renderATMs(atms) {
    // Clear existing markers
    Object.values(atmMarkers).forEach(m => mapInstance.removeLayer(m.marker));
    atmMarkers = {};

    // Populate quick jump dropdown
    const selectEl = document.getElementById("quickAtmSelect");
    if (selectEl) {
      selectEl.innerHTML = '<option value="">Jump to ATM...</option>';
      const sorted = [...atms].sort((a, b) => a.atm_id.localeCompare(b.atm_id));
      sorted.forEach(a => {
        const opt = document.createElement("option");
        opt.value = a.atm_id;
        opt.textContent = `${a.atm_id} (${a.zone_id.replace("ZONE_", "")})`;
        selectEl.appendChild(opt);
      });
      selectEl.onchange = (e) => {
        if (e.target.value) {
          this.centerATM(e.target.value);
        }
      };
    }

    atms.forEach(atm => {
      const isKiosk = atm.location_type === "STANDALONE_KIOSK";
      const markerColor = isKiosk ? "#d97706" : "#0d9488";

      const marker = L.circleMarker([atm.latitude, atm.longitude], {
        radius: isKiosk ? 6.5 : 5.5,
        fillColor: markerColor,
        color: "#ffffff",
        weight: 1.5,
        opacity: 0.9,
        fillOpacity: 0.85,
      }).addTo(mapInstance);

      // Contextual operational popup
      marker.bindPopup(`
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; color: #0f172a; min-width: 180px;">
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
            <b style="font-size: 13px; color: #0d9488;">${atm.atm_id}</b>
            <span style="font-size: 10px; font-weight: 700; color: #16a34a;">${atm.operating_status}</span>
          </div>
          <hr style="margin: 4px 0 6px 0; border: none; border-top: 1px solid #e2e8f0;">
          <div><b>Bank:</b> ${atm.bank_code.replace("BANK_", "").replace("_SYNTH", "")}</div>
          <div><b>Zone:</b> ${atm.zone_id.replace("ZONE_", "Zone ")}</div>
          <div><b>Type:</b> ${isKiosk ? "Standalone Kiosk" : "Branch Attached"}</div>
          <div><b>Capacity:</b> ${atm.cash_capacity_level}</div>
          <div><b>Historical Cashouts:</b> ${atm.historical_cashout_count}</div>
        </div>
      `);

      // Interactive click updates the Selected Location panel below map
      marker.on("click", () => {
        this.selectATM(atm, false);
      });

      atmMarkers[atm.atm_id] = { marker, data: atm };
    });
  },

  selectATM(atm, isPredictedTarget = false) {
    currentlySelectedAtmId = atm.atm_id;

    const idEl = document.getElementById("selAtmId");
    const statusEl = document.getElementById("selAtmStatus");
    const bankEl = document.getElementById("selAtmBank");
    const zoneEl = document.getElementById("selAtmZone");
    const typeEl = document.getElementById("selAtmType");
    const capEl = document.getElementById("selAtmCapacity");
    const cashoutsEl = document.getElementById("selAtmCashouts");
    const coordsEl = document.getElementById("selAtmCoords");
    const advisoryEl = document.getElementById("selectedLocationAdvisory");
    const detailsRow = document.getElementById("selectedLocationDetails");
    const centerBtn = document.getElementById("btnCenterSelectedAtm");

    if (idEl) idEl.innerText = atm.atm_id;
    if (statusEl) {
      statusEl.className = isPredictedTarget ? "priority-tag priority-critical" : "status-badge-online";
      statusEl.innerText = isPredictedTarget ? "TARGET ALERT" : (atm.operating_status || "OPERATIONAL");
    }
    if (bankEl) bankEl.innerText = atm.bank_code ? atm.bank_code.replace("BANK_", "").replace("_SYNTH", "") : "BANK";
    if (zoneEl) zoneEl.innerText = `${atm.zone_id ? atm.zone_id.replace("ZONE_", "Zone ") : "Sector"} · Metro Jurisdiction`;

    const isKiosk = atm.location_type === "STANDALONE_KIOSK";
    if (typeEl) typeEl.innerText = isKiosk ? "Standalone Kiosk" : "Branch Attached";
    if (capEl) capEl.innerText = `${atm.cash_capacity_level || "Standard"} Dispenser`;
    if (cashoutsEl) cashoutsEl.innerText = `${atm.historical_cashout_count || 0} recorded`;
    if (coordsEl) coordsEl.innerText = `${Number(atm.latitude).toFixed(4)}° N, ${Number(atm.longitude).toFixed(4)}° E`;

    if (detailsRow) detailsRow.style.display = "grid";
    if (centerBtn) centerBtn.style.display = "inline-block";

    if (advisoryEl) {
      advisoryEl.style.display = "block";
      if (isPredictedTarget) {
        advisoryEl.innerHTML = `<b style="color: var(--risk-critical);">&#9888; FORECASTED INTERCEPT TARGET:</b> High-probability cash-out convergence. Establish immediate 500m containment perimeter and deploy nearest patrol unit.`;
        advisoryEl.style.borderLeftColor = "var(--risk-critical)";
        advisoryEl.style.backgroundColor = "var(--risk-critical-bg)";
      } else {
        advisoryEl.innerHTML = `<b>Operational Notes:</b> ${isKiosk ? "Unmanned standalone kiosk with elevated vulnerability. Recommended drive-by corridor check." : "Branch-attached ATM facility with standard CCTV surveillance."}`;
        advisoryEl.style.borderLeftColor = "var(--accent-teal)";
        advisoryEl.style.backgroundColor = "#ffffff";
      }

      // Contextual check for active repeated convergence on this ATM or zone
      if (window.lastConvergencesData && Array.isArray(window.lastConvergencesData.convergences)) {
        const atmConv = window.lastConvergencesData.convergences.find(c => c.convergence_type === "ATM_CONVERGENCE" && c.target_id === atm.atm_id);
        const zoneConv = window.lastConvergencesData.convergences.find(c => c.convergence_type === "ZONE_CONVERGENCE" && c.zone_id === atm.zone_id);
        if (atmConv) {
          advisoryEl.innerHTML += `<div class="conv-advisory-banner">&#9888; <b>Repeated Target Convergence:</b> ${atmConv.total_matches} incidents (${atmConv.prediction_count} alerts) converged on this ATM in past ${atmConv.time_span_hours}h (Score: ${atmConv.convergence_score}/100, ${atmConv.severity_level}).</div>`;
        } else if (zoneConv) {
          advisoryEl.innerHTML += `<div class="conv-advisory-banner">&#9888; <b>Regional Corridor Convergence:</b> Active zone convergence in ${atm.zone_id ? atm.zone_id.replace("ZONE_", "Zone ") : "this zone"} across ${zoneConv.involved_atm_ids.length} ATMs (${zoneConv.total_matches} incidents).</div>`;
        }
      }
    }

    // Sync dropdown if exists
    const selectEl = document.getElementById("quickAtmSelect");
    if (selectEl && selectEl.value !== atm.atm_id) {
      selectEl.value = atm.atm_id;
    }
  },

  centerATM(atmId) {
    const item = atmMarkers[atmId];
    if (!item) return;
    mapInstance.flyTo([item.data.latitude, item.data.longitude], 14.5, { duration: 0.8 });
    item.marker.openPopup();
    this.selectATM(item.data, false);
  },

  setupPanelListeners() {
    const centerBtn = document.getElementById("btnCenterSelectedAtm");
    if (centerBtn) {
      centerBtn.onclick = () => {
        if (currentlySelectedAtmId) {
          this.centerATM(currentlySelectedAtmId);
        }
      };
    }
  },

  filterByZone(zoneId) {
    currentZoneFilter = zoneId;

    if (zoneId === "ALL") {
      Object.values(atmMarkers).forEach(({ marker }) => {
        marker.setStyle({ opacity: 0.9, fillOpacity: 0.85 });
      });
      mapInstance.flyTo([28.6300, 77.2000], 11, { duration: 0.8 });
      return;
    }

    Object.values(atmMarkers).forEach(({ marker, data }) => {
      if (data.zone_id === zoneId) {
        marker.setStyle({ opacity: 1.0, fillOpacity: 0.95 });
      } else {
        marker.setStyle({ opacity: 0.15, fillOpacity: 0.1 });
      }
    });

    const center = ZONE_CENTERS[zoneId];
    if (center) {
      mapInstance.flyTo([center.lat, center.lon], 12.5, { duration: 0.8 });
    }
  },

  highlightPrediction(predictedAtmId, topCandidates = []) {
    // Remove existing target layer
    if (targetHighlightLayer) {
      mapInstance.removeLayer(targetHighlightLayer);
      targetHighlightLayer = null;
    }

    const target = atmMarkers[predictedAtmId];
    if (!target) return;

    const lat = target.data.latitude;
    const lon = target.data.longitude;

    // Pan with smooth animation
    mapInstance.flyTo([lat, lon], 14, { duration: 1.0 });

    // Create tactical intercept perimeter group
    const group = L.layerGroup();

    // 1. Tactical perimeter radius (500 meters containment zone)
    const bufferCircle = L.circle([lat, lon], {
      radius: 500,
      color: "#dc2626",
      fillColor: "#dc2626",
      fillOpacity: 0.14,
      weight: 2,
      dashArray: "4, 6",
    });
    group.addLayer(bufferCircle);

    // 2. High-visibility red target marker
    const targetPin = L.circleMarker([lat, lon], {
      radius: 11,
      color: "#ffffff",
      fillColor: "#dc2626",
      fillOpacity: 1,
      weight: 3,
    });
    group.addLayer(targetPin);

    // 3. Highlight Secondary Candidates (Ranks 2-5)
    topCandidates.slice(1).forEach(cand => {
      const candItem = atmMarkers[cand.atm_id];
      if (candItem) {
        const secondaryMarker = L.circleMarker([candItem.data.latitude, candItem.data.longitude], {
          radius: 8,
          color: "#ffffff",
          fillColor: "#ea580c",
          fillOpacity: 0.85,
          weight: 2,
        });
        secondaryMarker.bindTooltip(`Rank #${cand.rank}: ${cand.atm_id} (${(cand.probability * 100).toFixed(1)}%)`, {
          direction: "top",
        });
        group.addLayer(secondaryMarker);
      }
    });

    group.addTo(mapInstance);
    targetHighlightLayer = group;

    // Open target popup with prediction details
    target.marker.openPopup();

    // Automatically populate Selected Location panel with target telemetry
    this.selectATM(target.data, true);
  },

  focusLocation(lat, lon, zoom = 14) {
    if (mapInstance && lat && lon) {
      mapInstance.flyTo([lat, lon], zoom, { duration: 0.8 });
    }
  },

  selectAtmById(atmId) {
    const item = atmMarkers[atmId];
    if (item) {
      this.selectATM(item.data, true);
      mapInstance.flyTo([item.data.latitude, item.data.longitude], 15, { duration: 0.8 });
    }
  },
};
