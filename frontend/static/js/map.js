/**
 * Geospatial Map Controller using Leaflet.js.
 * Displays ATM locations, administrative zones, and real-time prediction tactical overlays.
 */

let mapInstance = null;
let atmMarkers = {};
let targetHighlightLayer = null;
let zonePolygons = [];
let currentZoneFilter = "ALL";

const ZONE_CENTERS = {
  ZONE_CENTRAL: { lat: 28.6300, lon: 77.2200, name: "Central Commercial Core", color: "#38bdf8" },
  ZONE_NORTH:   { lat: 28.7000, lon: 77.1500, name: "North Transport Nexus", color: "#06b6d4" },
  ZONE_SOUTH:   { lat: 28.5300, lon: 77.2000, name: "South Institutional Hub", color: "#a855f7" },
  ZONE_EAST:    { lat: 28.6200, lon: 77.2900, name: "East Industrial Fringe", color: "#f97316" },
  ZONE_WEST:    { lat: 28.6500, lon: 77.1000, name: "West Market Corridor", color: "#10b981" },
};

export const MapController = {
  init(containerId = "map") {
    if (mapInstance) return mapInstance;

    // Center on Metropolitan Simulation Coordinates
    mapInstance = L.map(containerId, {
      center: [28.6300, 77.2000],
      zoom: 11,
      minZoom: 10,
      maxZoom: 16,
    });

    // Native dark canvas basemap (Esri World Dark Gray Base - key-free, no watermarks, no inverted road shields)
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
      maxZoom: 16,
    }).addTo(mapInstance);

    this.renderZones();
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
        fillOpacity: 0.08,
        weight: 1.5,
        dashArray: "4, 6",
      }).addTo(mapInstance);

      circle.bindTooltip(`<b>${zoneId}</b><br>${z.name}`, {
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

    atms.forEach(atm => {
      const isKiosk = atm.location_type === "STANDALONE_KIOSK";
      const markerColor = isKiosk ? "#f59e0b" : "#38bdf8";

      const marker = L.circleMarker([atm.latitude, atm.longitude], {
        radius: isKiosk ? 6.5 : 5.5,
        fillColor: markerColor,
        color: "#ffffff",
        weight: 1,
        opacity: 0.75,
        fillOpacity: 0.7,
      }).addTo(mapInstance);

      marker.bindPopup(`
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; color: #0f172a; min-width: 175px;">
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
            <b style="font-size: 13px; color: #0284c7;">${atm.atm_id}</b>
            <span style="font-size: 10px; font-weight: 700; color: #10b981;">${atm.operating_status}</span>
          </div>
          <hr style="margin: 4px 0 6px 0; border: none; border-top: 1px solid #cbd5e1;">
          <div><b>Bank:</b> ${atm.bank_code.replace("BANK_", "").replace("_SYNTH", "")}</div>
          <div><b>Zone:</b> ${atm.zone_id}</div>
          <div><b>Type:</b> ${isKiosk ? "Standalone Kiosk" : "Branch Attached"}</div>
          <div><b>Capacity:</b> ${atm.cash_capacity_level}</div>
          <div><b>Historical Cashouts:</b> ${atm.historical_cashout_count}</div>
        </div>
      `);

      atmMarkers[atm.atm_id] = { marker, data: atm };
    });
  },

  filterByZone(zoneId) {
    currentZoneFilter = zoneId;

    if (zoneId === "ALL") {
      Object.values(atmMarkers).forEach(({ marker }) => {
        marker.setStyle({ opacity: 0.75, fillOpacity: 0.7 });
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

    // Pan with animation
    mapInstance.flyTo([lat, lon], 14, { duration: 1.0 });

    // Create tactical intercept perimeter group
    const group = L.layerGroup();

    // 1. Tactical perimeter radius (500 meters)
    const bufferCircle = L.circle([lat, lon], {
      radius: 500,
      color: "#ef4444",
      fillColor: "#ef4444",
      fillOpacity: 0.2,
      weight: 2,
      dashArray: "3, 6",
    });
    group.addLayer(bufferCircle);

    // 2. High-visibility pulsing target marker
    const targetPin = L.circleMarker([lat, lon], {
      radius: 12,
      color: "#ffffff",
      fillColor: "#ef4444",
      fillOpacity: 1,
      weight: 3,
    });
    group.addLayer(targetPin);

    // 3. Highlight Secondary Candidates (Ranks 2-5)
    topCandidates.slice(1).forEach(cand => {
      const candItem = atmMarkers[cand.atm_id];
      if (candItem) {
        const secondaryMarker = L.circleMarker([candItem.data.latitude, candItem.data.longitude], {
          radius: 8.5,
          color: "#f59e0b",
          fillColor: "#f59e0b",
          fillOpacity: 0.75,
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
  },
};
