import { useApi } from "../hooks/useApi";
import RadialGauge from "./RadialGauge";
import SeverityBadge from "./SeverityBadge";

function riskLevelKey(prob) {
  if (prob == null) return "low";
  if (prob >= 0.80) return "critical";
  if (prob >= 0.60) return "high";
  if (prob >= 0.40) return "medium";
  return "low";
}

const DISTRICT_INFO = {
  Gakenke: { color: "#6C9AB5" },
  Burera:  { color: "#74936A" },
  Musanze: { color: "#C99A3E" },
  Gicumbi: { color: "#C24B3A" },
};

const styles = {
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 },
  card: {
    background: "var(--panel)", border: "1px solid var(--line-strong)",
    borderRadius: 10, padding: "18px 20px",
  },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  districtName: { fontSize: 15, fontWeight: 700 },
  ringRow: { display: "flex", alignItems: "center", gap: 16, marginBottom: 14 },
  statCol: { display: "flex", flexDirection: "column", gap: 10, flex: 1, minWidth: 0 },
  statLabel: { fontSize: 10.5, color: "var(--chalk-dim)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 },
  statValue: { fontSize: 16, fontWeight: 700 },
  divider: { height: 1, background: "var(--line-strong)", margin: "12px 0" },
  meta: { fontSize: 11, color: "var(--chalk-dim)" },
  loadingCard: {
    background: "var(--panel)", border: "1px solid var(--line-strong)",
    borderRadius: 10, padding: "18px 20px", color: "var(--chalk-dim)",
  },
};

export default function DistrictCards() {
  const { data, loading, error } = useApi("/api/districts");
  const districts = data?.districts || [];

  if (loading) return (
    <div style={styles.grid}>
      {["Gakenke", "Burera", "Musanze", "Gicumbi"].map((d) => (
        <div key={d} style={styles.loadingCard}>Loading {d}…</div>
      ))}
    </div>
  );

  if (error) return <div style={{ color: "var(--ember-text)" }}>Error loading districts: {error}</div>;

  return (
    <div style={styles.grid}>
      {districts.map((d) => {
        const info = DISTRICT_INFO[d.district] || { color: "var(--chalk-dim)" };
        const prob = d.highest_risk_probability;

        return (
          <div key={d.district} style={{ ...styles.card, borderTop: `3px solid ${info.color}` }}>
            <div style={styles.header}>
              <span style={{ ...styles.districtName, color: info.color }}>{d.district}</span>
              <SeverityBadge
                level={d.alert_level || "NORMAL"}
                label={d.alert_level || "STABLE"}
              />
            </div>

            <div style={styles.ringRow}>
              {prob != null
                ? <RadialGauge value={prob * 100} level={riskLevelKey(prob)} label="Peak risk" size={74} />
                : <RadialGauge value={0} level="low" label="No data" size={74} />}

              <div style={styles.statCol}>
                <div>
                  <div style={styles.statLabel}>Slope units monitored</div>
                  <div style={styles.statValue}>{d.unit_count ?? "—"}</div>
                </div>
                <div>
                  <div style={styles.statLabel}>Alerts (7d)</div>
                  <div style={{ ...styles.statValue, color: d.recent_alert_count > 0 ? "var(--ember-text)" : "var(--chalk)" }}>
                    {d.recent_alert_count ?? 0}
                  </div>
                </div>
              </div>
            </div>

            {d.alert_level && (
              <>
                <div style={styles.divider} />
                <div style={{ fontSize: 12, color: "var(--chalk-dim)", marginBottom: 10 }}>
                  Highest risk in <strong style={{ color: "var(--chalk)" }}>{d.highest_risk_sector || "unknown sector"}</strong>
                </div>
              </>
            )}

            <div style={styles.meta}>
              Last update: {d.last_update || "No data yet"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
