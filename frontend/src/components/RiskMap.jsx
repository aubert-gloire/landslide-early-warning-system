import { useEffect, useRef } from "react";
import L from "leaflet";
import { useApi } from "../hooks/useApi";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

// Risk colour scale — high contrast for field use
const RISK_COLORS = {
  critical: "#dc2626",
  high:     "#ea580c",
  medium:   "#ca8a04",
  low:      "#16a34a",
};

const ALERT_LEVEL_COLORS = {
  EMERGENCY: "#dc2626",
  WARNING:   "#ea580c",
  WATCH:     "#ca8a04",
};

function riskColor(level) {
  return RISK_COLORS[level] || "#64748b";
}

const styles = {
  container: { position: "relative", width: "100%", height: "100%" },
  map: { width: "100%", height: "100%", borderRadius: "8px" },
  legend: {
    position: "absolute", bottom: 24, right: 12, zIndex: 1000,
    background: "rgba(15,17,23,0.92)", border: "1px solid #334155",
    borderRadius: 6, padding: "10px 14px", fontSize: 12,
  },
  legendRow: { display: "flex", alignItems: "center", gap: 8, marginBottom: 4 },
  dot: { width: 12, height: 12, borderRadius: "50%", flexShrink: 0 },
  overlay: {
    position: "absolute", inset: 0, display: "flex", alignItems: "center",
    justifyContent: "center", background: "rgba(15,17,23,0.82)", zIndex: 500,
    borderRadius: "8px",
  },
};

export default function RiskMap() {
  const { data, loading, error } = useApi("/api/risk-map");
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const layerRef = useRef(null);

  // Initialize Leaflet map once — mapRef.current is always set because the
  // container div renders unconditionally (no early return above it).
  useEffect(() => {
    if (mapInstance.current || !mapRef.current) return;
    mapInstance.current = L.map(mapRef.current, {
      center: [-1.45, 29.85],
      zoom: 10,
      zoomControl: true,
      zoomSnap: 0.25,        // allow quarter-level zoom increments
      zoomDelta: 0.5,        // each scroll tick = half a zoom level
      wheelPxPerZoomLevel: 120, // require more scroll movement per level
      doubleClickZoom: false, // prevent accidental full zoom on double click
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(mapInstance.current);

    return () => {
      mapInstance.current?.remove();
      mapInstance.current = null;
    };
  }, []);

  // Add district boundary overlay once
  useEffect(() => {
    if (!mapInstance.current) return;
    fetch(`${API_BASE}/api/boundary`)
      .then(r => r.ok ? r.json() : null)
      .then(geojson => {
        if (!geojson || !mapInstance.current) return;
        L.geoJSON(geojson, {
          style: { color: "#f8fafc", weight: 2, fillOpacity: 0, dashArray: "4 3" },
          onEachFeature: (f, layer) => {
            if (f.properties?.NAME_2) layer.bindTooltip(f.properties.NAME_2, { permanent: false, className: "" });
          },
        }).addTo(mapInstance.current);
      })
      .catch(() => {});
  }, []);

  // Update GeoJSON layer when data arrives
  useEffect(() => {
    if (!mapInstance.current || !data?.features) return;

    if (layerRef.current) {
      mapInstance.current.removeLayer(layerRef.current);
    }

    layerRef.current = L.geoJSON(data, {
      style: (feature) => ({
        fillColor: riskColor(feature.properties.risk_level),
        fillOpacity: 0.65,
        color: "#1e293b",
        weight: 1,
      }),
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        const pct = Math.round(p.risk_probability * 100);
        const topFeatures = p.top_features || [];
        const maxImp = topFeatures.length ? Math.max(...topFeatures.map(([, imp]) => imp), 0.001) : 1;
        const driversHtml = topFeatures.length
          ? topFeatures.map(([name, imp]) =>
              `<div style="margin-top:4px">
                <span style="color:#94a3b8">${name.replace(/_/g, " ")}</span>
                <span style="float:right;color:#64748b">${(imp * 100).toFixed(1)}%</span>
                <div style="height:3px;background:#1d4ed8;width:${Math.round((imp/maxImp)*100)}%;border-radius:2px;margin-top:2px"></div>
              </div>`
            ).join("")
          : "";
        const locationStr = p.sector
          ? `${p.district} / ${p.sector} sector`
          : p.district;

        const alertLevelHtml = p.alert_triggered && p.alert_level
          ? `<span style="display:inline-block;padding:2px 8px;border-radius:10px;
              background:${ALERT_LEVEL_COLORS[p.alert_level] || "#dc2626"}22;
              color:${ALERT_LEVEL_COLORS[p.alert_level] || "#dc2626"};
              font-size:11px;font-weight:700;margin-left:6px">${p.alert_level}</span>`
          : "";

        const popup = L.popup({ maxWidth: 300 });
        layer.bindPopup(popup);
        layer.on("click", async () => {
          // Fetch sparkline data
          let sparkHtml = "";
          try {
            const res = await fetch(`${API_BASE}/api/units/${p.unit_id}/rainfall?days=10`);
            if (res.ok) {
              const rain = await res.json();
              const vals = rain.days.map(d => d.daily_mm);
              const maxVal = Math.max(...vals, 1);
              const bars = vals.map((v, i) => {
                const h = Math.max(2, Math.round((v / maxVal) * 36));
                const date = rain.days[i]?.date?.slice(5) || "";
                return `<div title="${date}: ${v}mm" style="flex:1;display:flex;flex-direction:column;
                  align-items:center;justify-content:flex-end;height:40px">
                  <div style="width:100%;background:#3b82f6;border-radius:2px 2px 0 0;height:${h}px"></div>
                </div>`;
              }).join("");
              sparkHtml = `<div style="margin-top:10px;padding-top:8px;border-top:1px solid #1e293b">
                <div style="font-size:11px;color:#64748b;margin-bottom:4px">10-day rainfall (mm)</div>
                <div style="display:flex;gap:1px;height:40px;align-items:flex-end">${bars}</div>
                <div style="display:flex;justify-content:space-between;font-size:9px;color:#475569;margin-top:2px">
                  <span>${rain.days[0]?.date?.slice(5) || ""}</span>
                  <span>${rain.days[rain.days.length-1]?.date?.slice(5) || ""}</span>
                </div>
              </div>`;
            }
          } catch(_) {}

          popup.setContent(
            `<div style="font-size:13px;line-height:1.6;min-width:240px;background:#111827;color:#e2e8f0;padding:4px">
              <strong style="font-size:14px">${locationStr}</strong>${alertLevelHtml}<br/>
              <span style="color:#64748b;font-size:11px">Unit ${p.unit_id}</span><br/>
              <span style="color:${riskColor(p.risk_level)};font-weight:700;font-size:15px">${pct}%</span>
              <span style="color:#94a3b8;font-size:12px"> — ${p.risk_level} risk</span>
              ${p.alert_triggered ? '<div style="color:#dc2626;font-weight:600;margin-top:4px">⚠ ALERT DISPATCHED</div>' : ""}
              ${driversHtml ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid #1e293b">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Top Drivers</div>
                ${driversHtml}
              </div>` : ""}
              ${sparkHtml}
              <div style="margin-top:8px;font-size:11px;color:#475569">${p.date}</div>
            </div>`
          );
        });
      },
    }).addTo(mapInstance.current);

    if (data.features.length > 0) {
      mapInstance.current.fitBounds(layerRef.current.getBounds(), { padding: [20, 20] });
    }
  }, [data]);

  return (
    <div style={styles.container}>
      <div ref={mapRef} style={styles.map} />
      {loading && (
        <div style={styles.overlay}>
          <span style={{ color: "#94a3b8" }}>Loading risk map…</span>
        </div>
      )}
      {error && (
        <div style={styles.overlay}>
          <span style={{ color: "#f87171" }}>Map error: {error}</span>
        </div>
      )}
      <div style={styles.legend}>
        <div style={{ fontWeight: 600, marginBottom: 8, color: "#e2e8f0" }}>Risk Level</div>
        {Object.entries(RISK_COLORS).map(([level, color]) => (
          <div key={level} style={styles.legendRow}>
            <div style={{ ...styles.dot, background: color }} />
            <span style={{ color: "#cbd5e1", textTransform: "capitalize" }}>{level}</span>
          </div>
        ))}
        {data?.metadata && (
          <div style={{ marginTop: 8, color: "#64748b", fontSize: 11 }}>
            {data.metadata.unit_count} units · {data.metadata.date}
          </div>
        )}
      </div>
    </div>
  );
}
