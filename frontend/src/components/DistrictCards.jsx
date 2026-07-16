import { useApi } from "../hooks/useApi";
import RadialGauge from "./RadialGauge";

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

function riskBg(prob) {
  if (prob == null) return "var(--panel-2)";
  if (prob >= 0.80) return "rgba(194,75,58,0.15)";
  if (prob >= 0.60) return "rgba(201,154,62,0.12)";
  if (prob >= 0.40) return "rgba(201,154,62,0.08)";
  return "rgba(116,147,106,0.12)";
}

function riskLabel(prob) {
  if (prob == null) return "No data";
  if (prob >= 0.80) return "CRITICAL";
  if (prob >= 0.60) return "HIGH";
  if (prob >= 0.40) return "MEDIUM";
  return "LOW";
}

function riskTextColor(prob) {
  if (prob == null) return "var(--chalk-dim)";
  if (prob >= 0.80) return "var(--ember-text)";
  if (prob >= 0.60) return "var(--amber-text)";
  if (prob >= 0.40) return "var(--amber-text)";
  return "var(--moss-text)";
}

function riskBorderColor(prob) {
  if (prob == null) return "var(--line)";
  if (prob >= 0.80) return "rgba(194,75,58,0.4)";
  if (prob >= 0.60) return "rgba(201,154,62,0.35)";
  if (prob >= 0.40) return "rgba(201,154,62,0.25)";
  return "rgba(116,147,106,0.3)";
}

const styles = {
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 },
  card: {
    background: "var(--panel)", border: "1px solid var(--line-strong)",
    borderRadius: 10, padding: "18px 20px",
  },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 },
  districtName: { fontSize: 15, fontWeight: 700 },
  riskBadge: (prob) => ({
    fontSize: 11, fontWeight: 700, letterSpacing: "0.05em",
    padding: "3px 10px", borderRadius: 20,
    background: riskBg(prob), color: riskTextColor(prob),
    border: `1px solid ${riskBorderColor(prob)}`,
  }),
  stat: { marginBottom: 10 },
  statLabel: { fontSize: 11, color: "var(--chalk-dim)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 },
  statValue: { fontSize: 18, fontWeight: 700 },
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
              <span style={styles.riskBadge(prob)}>{riskLabel(prob)}</span>
            </div>

            <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>
              {prob != null
                ? <RadialGauge value={prob * 100} level={riskLevelKey(prob)} label="Peak risk today" size={80} />
                : <span style={{ fontSize: 12, color: "var(--chalk-dim)" }}>No data yet</span>}
            </div>

            <div style={styles.stat}>
              <div style={styles.statLabel}>Slope units monitored</div>
              <div style={{ ...styles.statValue, color: "var(--chalk)", fontSize: 15 }}>
                {d.unit_count ?? "—"}
              </div>
            </div>

            <div style={styles.divider} />

            <div style={styles.stat}>
              <div style={styles.statLabel}>Alerts (last 7 days)</div>
              <div style={{ ...styles.statValue, color: d.recent_alert_count > 0 ? "var(--ember-text)" : "var(--chalk)", fontSize: 15 }}>
                {d.recent_alert_count ?? 0}
              </div>
            </div>

            {d.alert_level && (
              <div style={{
                marginBottom: 10, padding: "6px 10px", borderRadius: 6,
                background: d.alert_level === "EMERGENCY" ? "rgba(194,75,58,0.15)" : "rgba(201,154,62,0.12)",
                fontSize: 12, fontWeight: 600,
                color: d.alert_level === "EMERGENCY" ? "var(--ember-text)" : "var(--amber-text)",
              }}>
                ⚠ {d.alert_level} — {d.highest_risk_sector || ""}
              </div>
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
