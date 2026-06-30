import { useEffect, useRef } from "react";
import L from "leaflet";
import { useApi } from "../hooks/useApi";

// Risk colour scale — high contrast for field use
const RISK_COLORS = {
  critical: "#dc2626",  // red
  high:     "#ea580c",  // orange
  medium:   "#ca8a04",  // amber
  low:      "#16a34a",  // green
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
  error: { color: "#f87171", padding: 16 },
  loading: { color: "#94a3b8", padding: 16 },
};

export default function RiskMap() {
  const { data, loading, error } = useApi("/api/risk-map");
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const layerRef = useRef(null);

  // Initialize Leaflet map once
  useEffect(() => {
    if (mapInstance.current) return;
    mapInstance.current = L.map(mapRef.current, {
      center: [-1.45, 29.85],
      zoom: 10,
      zoomControl: true,
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
        const topF = (p.top_features || []).map(([name]) => name.replace(/_/g, " ")).join(", ");
        layer.bindPopup(
          `<div style="font-size:13px;line-height:1.6">
            <strong>${p.district}</strong> · Unit ${p.unit_id}<br/>
            Risk: <strong style="color:${riskColor(p.risk_level)}">${pct}% (${p.risk_level})</strong><br/>
            ${p.alert_triggered ? '<span style="color:#dc2626">⚠ ALERT DISPATCHED</span><br/>' : ""}
            ${topF ? `Drivers: ${topF}` : ""}
          </div>`
        );
      },
    }).addTo(mapInstance.current);

    if (data.features.length > 0) {
      mapInstance.current.fitBounds(layerRef.current.getBounds(), { padding: [20, 20] });
    }
  }, [data]);

  if (loading) return <div style={styles.loading}>Loading risk map…</div>;
  if (error) return <div style={styles.error}>Map error: {error}</div>;

  return (
    <div style={styles.container}>
      <div ref={mapRef} style={styles.map} />
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
