import { useState } from "react";
import { useApi } from "../hooks/useApi";

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

const STATUS_COLORS = {
  sent:      { bg: "rgba(116,147,106,0.12)", text: "var(--moss-text)" },
  delivered: { bg: "rgba(116,147,106,0.20)", text: "var(--moss-text)" },
  pending:   { bg: "var(--panel-2)",          text: "var(--chalk-dim)" },
  failed:    { bg: "rgba(194,75,58,0.15)",   text: "var(--ember-text)" },
};

const FEEDBACK_COLORS = {
  CONFIRMED: { bg: "rgba(108,154,181,0.15)", text: "var(--storm-text)" },
  DENIED:    { bg: "rgba(194,75,58,0.12)",   text: "var(--ember-text)" },
};

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
  badge: (style) => ({
    display: "inline-block", padding: "2px 8px", borderRadius: 12,
    fontSize: 11, fontWeight: 600, background: style.bg, color: style.text,
  }),
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
              {["Sent at", "District", "Unit ID", "Risk %", "Status", "Officer Feedback"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={styles.empty}>Loading…</td></tr>
            ) : alerts.length === 0 ? (
              <tr><td colSpan={6} style={styles.empty}>
                No alerts found{district ? ` for ${district}` : ""} — alerts are dispatched when a slope unit exceeds the production risk threshold
              </td></tr>
            ) : alerts.map((a) => {
              const statusStyle = STATUS_COLORS[a.delivery_status] || STATUS_COLORS.pending;
              const feedbackStyle = a.feedback ? FEEDBACK_COLORS[a.feedback] : null;
              const riskPct = a.risk_probability != null ? Math.round(a.risk_probability * 100) : null;
              return (
                <tr key={a.alert_id}>
                  <td style={{ ...styles.td, color: "var(--chalk-dim)", whiteSpace: "nowrap" }}>{formatDate(a.sent_at)}</td>
                  <td style={styles.td}>{a.district || "—"}</td>
                  <td style={{ ...styles.td, fontFamily: "'Space Mono', monospace", color: "var(--chalk-dim)" }}>{a.slope_unit_id || "—"}</td>
                  <td style={styles.td}>{riskPct != null ? `${riskPct}%` : "—"}</td>
                  <td style={styles.td}>
                    <span style={styles.badge(statusStyle)}>{a.delivery_status}</span>
                  </td>
                  <td style={styles.td}>
                    {feedbackStyle
                      ? <span style={styles.badge(feedbackStyle)}>{a.feedback}</span>
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
