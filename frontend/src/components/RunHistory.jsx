import { useState } from "react";
import { useApi } from "../hooks/useApi";
import RunHeatmap from "./RunHeatmap";

const DISTRICTS = ["Gakenke", "Burera", "Musanze", "Gicumbi"];
const PAGE_SIZE = 20;

function riskColor(p) {
  if (p == null) return "var(--chalk-dim)";
  if (p >= 0.80) return "var(--ember-text)";
  if (p >= 0.40) return "var(--amber-text)";
  return "var(--moss-text)";
}

function StatusBadge({ triggered }) {
  return triggered ? (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700,
      background: "rgba(194,75,58,0.14)", color: "var(--ember-text)",
      border: "1px solid rgba(194,75,58,0.35)", fontFamily: "'Space Mono', monospace",
      letterSpacing: "0.05em",
    }}>
      ALERT SENT
    </span>
  ) : (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700,
      background: "rgba(116,147,106,0.10)", color: "var(--moss-text)",
      border: "1px solid rgba(116,147,106,0.28)", fontFamily: "'Space Mono', monospace",
      letterSpacing: "0.05em",
    }}>
      MONITORING
    </span>
  );
}

function DistrictCell({ name, stats }) {
  if (!stats) return <span style={{ color: "var(--chalk-dim)" }}>—</span>;
  const pct = Math.round(stats.max_risk * 100);
  return (
    <span style={{ color: riskColor(stats.max_risk), fontFamily: "'Space Mono', monospace", fontSize: 12 }}>
      {pct}%{stats.alert_triggered ? " ⚠" : ""}
    </span>
  );
}

const styles = {
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: {
    textAlign: "left", padding: "8px 12px",
    color: "var(--chalk-dim)", fontSize: 11, letterSpacing: "0.05em",
    borderBottom: "1px solid var(--line)", whiteSpace: "nowrap",
  },
  td: { padding: "11px 12px", borderBottom: "1px solid var(--line)", verticalAlign: "middle" },
  empty: { color: "var(--chalk-dim)", padding: "40px 0", textAlign: "center" },
  btn: {
    background: "var(--panel)", border: "1px solid var(--line-strong)",
    color: "var(--chalk)", padding: "4px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12,
  },
};

export default function RunHistory() {
  const [page, setPage] = useState(0);
  const path = `/api/pipeline-runs?limit=${PAGE_SIZE}&skip=${page * PAGE_SIZE}`;
  const { data, loading, error, refetch } = useApi(path, [page]);

  const runs  = data?.runs  ?? [];
  const total = data?.total ?? 0;

  return (
    <div>
      <RunHeatmap refreshKey={page} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ color: "var(--chalk-dim)", fontSize: 12 }}>
          {total} pipeline runs recorded
        </span>
        <button style={styles.btn} onClick={refetch}>Refresh</button>
      </div>

      {error && (
        <div style={{ color: "var(--ember-text)", marginBottom: 12, fontSize: 13 }}>Error: {error}</div>
      )}

      <div style={{ overflowX: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["Date", "Action", "Rainfall", "Peak Risk", "Alerts", "SMS Sent", ...DISTRICTS, "Seismic"].map(h => (
                <th key={h} style={styles.th}>{h.toUpperCase()}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={11} style={styles.empty}>Loading…</td></tr>
            ) : runs.length === 0 ? (
              <tr><td colSpan={11} style={styles.empty}>
                No runs recorded yet — history is saved after each pipeline execution.
              </td></tr>
            ) : runs.map((r) => {
              const date = new Date(r.run_date + "T12:00:00Z").toLocaleDateString("en-GB", {
                day: "numeric", month: "short", year: "numeric",
              });
              const maxPct = r.max_risk_probability != null
                ? Math.round(r.max_risk_probability * 100) : null;

              return (
                <tr key={r._id} style={{
                  background: r.alerts_triggered > 0 ? "rgba(194,75,58,0.04)" : "transparent",
                }}>
                  <td style={{ ...styles.td, fontFamily: "'Space Mono', monospace", fontSize: 12, whiteSpace: "nowrap" }}>
                    {date}
                  </td>
                  <td style={styles.td}>
                    <StatusBadge triggered={r.alerts_triggered > 0} />
                  </td>
                  <td style={{ ...styles.td, fontSize: 12 }}>
                    {r.rainfall_available === false
                      ? <span style={{ color: "var(--amber-text)" }}>Terrain-only</span>
                      : <span style={{ color: "var(--moss-text)" }}>OK</span>}
                  </td>
                  <td style={{ ...styles.td, fontFamily: "'Space Mono', monospace" }}>
                    <span style={{ color: riskColor(r.max_risk_probability) }}>
                      {maxPct != null ? `${maxPct}%` : "—"}
                    </span>
                  </td>
                  <td style={{ ...styles.td, fontFamily: "'Space Mono', monospace", color: r.alerts_triggered > 0 ? "var(--ember-text)" : "var(--chalk-dim)" }}>
                    {r.alerts_triggered ?? 0}
                  </td>
                  <td style={{ ...styles.td, fontFamily: "'Space Mono', monospace", color: "var(--chalk-dim)" }}>
                    {r.sms_sent ?? 0}
                  </td>
                  {DISTRICTS.map(d => (
                    <td key={d} style={styles.td}>
                      <DistrictCell name={d} stats={r.districts?.[d]} />
                    </td>
                  ))}
                  <td style={{ ...styles.td, color: r.seismic_detected ? "var(--amber-text)" : "var(--chalk-dim)", fontSize: 12 }}>
                    {r.seismic_detected ? "YES" : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {total > PAGE_SIZE && (
        <div style={{ display: "flex", gap: 8, marginTop: 14, alignItems: "center" }}>
          <button style={styles.btn} disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span style={{ color: "var(--chalk-dim)", fontSize: 12 }}>
            Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}
          </span>
          <button style={styles.btn} disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
