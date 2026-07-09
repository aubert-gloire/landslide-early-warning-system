import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { useApi } from "../hooks/useApi";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

const RISK_COLORS = { low: "#74936A", moderate: "#C99A3E", high: "#C24B3A" };

function riskBand(p) {
  if (p >= 0.8) return "high";
  if (p >= 0.5) return "moderate";
  return "low";
}

export default function RiskMap() {
  const containerRef = useRef(null);
  const mapRef       = useRef(null);
  const layerRef     = useRef(null);
  const { data, loading, error } = useApi("/api/risk-map");

  // Initialise map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { zoomControl: false }).setView([-1.58, 29.83], 10);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 16,
    }).addTo(map);
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Redraw slope-unit markers when data changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;
    if (layerRef.current) layerRef.current.remove();

    layerRef.current = L.geoJSON(data, {
      style: (feature) => {
        const band = riskBand(feature.properties.risk_probability);
        return {
          fillColor:   RISK_COLORS[band],
          color:       "#14171A",
          weight:      0.5,
          fillOpacity: 0.75,
        };
      },
      onEachFeature: (f, lyr) => {
        const p = f.properties;
        lyr.bindPopup(
          `<strong>Unit ${p.unit_id}</strong> &middot; ${p.district}<br/>` +
          `Risk: ${(p.risk_probability * 100).toFixed(0)}%<br/>` +
          (p.alert_triggered ? "<span style='color:#E2836F'>&#9888; SMS alert dispatched</span>" : "Below alert threshold")
        );
        lyr.on("mouseover", () => lyr.setStyle({ fillOpacity: 1, weight: 1.5 }));
        lyr.on("mouseout",  () => lyr.setStyle({ fillOpacity: 0.75, weight: 0.5 }));
      },
    }).addTo(map);

    return () => layerRef.current && layerRef.current.remove();
  }, [data]);

  const meta = data?.metadata ?? {};
  const runDate  = meta.run_date  ? new Date(meta.run_date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : null;
  const dataDate = meta.data_date ? new Date(meta.data_date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : null;
  const status = loading ? "Loading…" : error ? `Error: ${error}` : `${meta.unit_count ?? data?.features?.length ?? 0} slope units`;

  return (
    <div style={{
      position: "relative", width: "100%", height: "520px",
      borderRadius: 14, overflow: "hidden", border: "1px solid var(--line-strong)",
    }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {loading && (
        <div style={{
          position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(20,23,26,0.7)", color: "var(--chalk-dim)",
          fontFamily: "'Space Mono', monospace", fontSize: 13,
        }}>
          Loading slope units…
        </div>
      )}

      {/* Legend */}
      <div style={{
        position: "absolute", bottom: 12, left: 12, zIndex: 1000,
        background: "var(--panel)", border: "1px solid var(--line-strong)",
        borderRadius: 10, padding: "10px 14px", color: "var(--chalk)",
        fontFamily: "'Space Mono', monospace", fontSize: 11,
      }}>
        {[
          { color: "#74936A", label: "low (< 50%)" },
          { color: "#C99A3E", label: "moderate (50–79%)" },
          { color: "#C24B3A", label: "high (≥ 80%) — alert sent" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: color, display: "inline-block" }} />
            {label}
          </div>
        ))}
        <div style={{ marginTop: 8, borderTop: "1px solid var(--line)", paddingTop: 7, display: "flex", flexDirection: "column", gap: 2 }}>
          <div style={{ opacity: 0.7 }}>{status}</div>
          {runDate  && <div style={{ opacity: 0.6 }}>Assessment: {runDate}</div>}
          {dataDate && <div style={{ opacity: 0.6 }}>Rainfall data to: {dataDate}</div>}
          {dataDate && runDate && dataDate !== meta.run_date && (
            <div style={{ color: "var(--amber-text)", fontSize: 10, marginTop: 1 }}>IMERG/CHIRPS lag</div>
          )}
        </div>
      </div>
    </div>
  );
}
