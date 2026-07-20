import { useState } from "react";
import { useApi } from "../hooks/useApi";
import SeverityBadge from "./SeverityBadge";

function FeedbackStats() {
  const { data } = useApi("/api/alerts/stats");
  if (!data) return null;
  const { total_alerts, confirmed, denied, awaiting_feedback, confirmation_rate } = data;
  return (
    <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
      {[
        { label: "Total Alerts Sent",      value: total_alerts,       color: "var(--chalk-dim)" },
        { label: "Confirmed by Officers",  value: confirmed,           color: "var(--moss-text)" },
        { label: "Denied by Officers",     value: denied,              color: "var(--ember-text)" },
        { label: "Awaiting Feedback",      value: awaiting_feedback,   color: "var(--amber-text)" },
        { label: "Confirmation Rate",      value: `${confirmation_rate}%`, color: "var(--storm-text)" },
      ].map(({ label, value, color }) => (
        <div key={label} style={{
          flex: 1, minWidth: 120, background: "var(--panel)",
          border: "1px solid var(--line-strong)", borderRadius: 8, padding: "10px 14px",
        }}>
          <div style={{ fontSize: 20, fontWeight: 700, color }}>{value}</div>
          <div style={{ fontSize: 11, color: "var(--chalk-dim)", marginTop: 2 }}>{label}</div>
        </div>
      ))}
    </div>
  );
}

function formatDate(ts) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

const styles = {
  wrap: { overflowX: "auto" },
  controls: { display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" },
  input: {
    background: "var(--panel-2)", border: "1px solid var(--line-strong)", color: "var(--chalk)",
    padding: "6px 10px", borderRadius: 6, fontSize: 13,
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { textAlign: "left", padding: "8px 12px", color: "var(--chalk-dim)", borderBottom: "1px solid var(--line)", whiteSpace: "nowrap" },
  td: { padding: "10px 12px", borderBottom: "1px solid var(--line)", verticalAlign: "top" },
  empty: { color: "var(--chalk-dim)", padding: "32px 0", textAlign: "center" },
  pagination: { display: "flex", gap: 8, marginTop: 14, alignItems: "center" },
  btn: {
    background: "var(--panel)", border: "1px solid var(--line-strong)", color: "var(--chalk)",
    padding: "4px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12,
  },
};

const DISTRICTS = ["All", "Gakenke", "Burera", "Musanze", "Gicumbi"];
const PAGE_SIZE = 20;

export default function AlertTable() {
  const [district, setDistrict] = useState("");
  const [page, setPage] = useState(0);

  const path = `/api/alerts?limit=${PAGE_SIZE}&skip=${page * PAGE_SIZE}${district ? `&district=${district}` : ""}`;
  const { data, loading, error, refetch } = useApi(path, [district, page]);

  const alerts = data?.alerts || [];
  const total = data?.total || 0;

  return (
    <div>
      <FeedbackStats />
      <div style={styles.controls}>
        <select
          style={styles.input}
          value={district}
          onChange={(e) => { setDistrict(e.target.value === "All" ? "" : e.target.value); setPage(0); }}
        >
          {DISTRICTS.map((d) => <option key={d}>{d}</option>)}
        </select>
        <button style={styles.btn} onClick={refetch}>Refresh</button>
        <span style={{ color: "var(--chalk-dim)", fontSize: 12, alignSelf: "center" }}>
          {total} total alerts
        </span>
      </div>

      {error && <div style={{ color: "var(--ember-text)", marginBottom: 12 }}>Error: {error}</div>}

      <div style={styles.wrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["Sent at", "District", "Unit ID", "Risk %", "Data", "Status", "Officer Feedback"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={styles.empty}>Loading…</td></tr>
            ) : alerts.length === 0 ? (
              <tr><td colSpan={7} style={styles.empty}>
                No alerts found{district ? ` for ${district}` : ""} — alerts are dispatched when a slope unit exceeds the production risk threshold
              </td></tr>
            ) : alerts.map((a) => {
              const riskPct = a.risk_probability != null ? Math.round(a.risk_probability * 100) : null;
              return (
                <tr key={a.alert_id}>
                  <td style={{ ...styles.td, color: "var(--chalk-dim)", whiteSpace: "nowrap" }}>{formatDate(a.sent_at)}</td>
                  <td style={styles.td}>{a.district || "—"}</td>
                  <td style={{ ...styles.td, fontFamily: "'Space Mono', monospace", color: "var(--chalk-dim)" }}>{a.slope_unit_id || "—"}</td>
                  <td style={styles.td}>{riskPct != null ? `${riskPct}%` : "—"}</td>
                  <td style={styles.td}>
                    {a.rainfall_available === false
                      ? <SeverityBadge level="TERRAIN_ONLY" label="TERRAIN-ONLY" />
                      : <span style={{ color: "var(--chalk-dim)", fontSize: 11 }}>—</span>}
                  </td>
                  <td style={styles.td}>
                    {a.provider_status && Object.keys(a.provider_status).length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                        {Object.entries(a.provider_status).map(([provider, rawStatus]) => {
                          const error = a.provider_errors?.[provider];
                          const level = error ? "FAILED" : "SENT";
                          return (
                            <span key={provider} title={error || rawStatus} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                              <SeverityBadge level={level} label={`${provider}: ${rawStatus}`} />
                            </span>
                          );
                        })}
                      </div>
                    ) : (
                      <SeverityBadge level={(a.delivery_status || "pending").toUpperCase()} label={a.delivery_status || "pending"} />
                    )}
                  </td>
                  <td style={styles.td}>
                    {a.feedback
                      ? <SeverityBadge level={a.feedback} label={a.feedback} />
                      : <span style={{ color: "var(--chalk-dim)" }}>Awaiting reply</span>
                    }
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {total > PAGE_SIZE && (
        <div style={styles.pagination}>
          <button style={styles.btn} disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span style={{ color: "var(--chalk-dim)", fontSize: 12 }}>Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}</span>
          <button style={styles.btn} disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
