import { useApi } from "../hooks/useApi";

const DISTRICT_INFO = {
  Gakenke: { color: "#0ea5e9" },
  Burera:  { color: "#8b5cf6" },
  Musanze: { color: "#f59e0b" },
  Gicumbi: { color: "#10b981" },
};

function riskBg(prob) {
  if (prob == null) return "#1e293b";
  if (prob >= 0.80) return "#450a0a";
  if (prob >= 0.60) return "#431407";
  if (prob >= 0.40) return "#422006";
  return "#14532d";
}

function riskLabel(prob) {
  if (prob == null) return "No data";
  if (prob >= 0.80) return "CRITICAL";
  if (prob >= 0.60) return "HIGH";
  if (prob >= 0.40) return "MEDIUM";
  return "LOW";
}

function riskTextColor(prob) {
  if (prob == null) return "#64748b";
  if (prob >= 0.80) return "#fca5a5";
  if (prob >= 0.60) return "#fdba74";
  if (prob >= 0.40) return "#fcd34d";
  return "#86efac";
}

const styles = {
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 },
  card: {
    background: "#1e293b", border: "1px solid #334155",
    borderRadius: 10, padding: "18px 20px",
  },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 },
  districtName: { fontSize: 15, fontWeight: 700 },
  riskBadge: (prob) => ({
    fontSize: 11, fontWeight: 700, letterSpacing: "0.05em",
    padding: "3px 10px", borderRadius: 20,
    background: riskBg(prob), color: riskTextColor(prob),
    border: `1px solid ${riskTextColor(prob)}30`,
  }),
  stat: { marginBottom: 10 },
  statLabel: { fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 },
  statValue: { fontSize: 18, fontWeight: 700 },
  divider: { height: 1, background: "#334155", margin: "12px 0" },
  meta: { fontSize: 11, color: "#64748b" },
  loadingCard: {
    background: "#1e293b", border: "1px solid #334155",
    borderRadius: 10, padding: "18px 20px", color: "#475569",
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

  if (error) return <div style={{ color: "#f87171" }}>Error loading districts: {error}</div>;

  return (
    <div style={styles.grid}>
      {districts.map((d) => {
        const info = DISTRICT_INFO[d.district] || { color: "#64748b" };
        const prob = d.highest_risk_probability;

        return (
          <div key={d.district} style={{ ...styles.card, borderTop: `3px solid ${info.color}` }}>
            <div style={styles.header}>
              <span style={{ ...styles.districtName, color: info.color }}>{d.district}</span>
              <span style={styles.riskBadge(prob)}>{riskLabel(prob)}</span>
            </div>

            <div style={styles.stat}>
              <div style={styles.statLabel}>Peak risk today</div>
              <div style={{ ...styles.statValue, color: riskTextColor(prob) }}>
                {prob != null ? `${Math.round(prob * 100)}%` : "—"}
              </div>
            </div>

            <div style={styles.stat}>
              <div style={styles.statLabel}>Slope units monitored</div>
              <div style={{ ...styles.statValue, color: "#e2e8f0", fontSize: 15 }}>
                {d.unit_count ?? "—"}
              </div>
            </div>

            <div style={styles.divider} />

            <div style={styles.stat}>
              <div style={styles.statLabel}>Alerts (last 7 days)</div>
              <div style={{ ...styles.statValue, color: d.recent_alert_count > 0 ? "#fca5a5" : "#e2e8f0", fontSize: 15 }}>
                {d.recent_alert_count ?? 0}
              </div>
            </div>

            <div style={styles.meta}>
              Last update: {d.last_update || "No data yet"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
