import { useApi } from "../hooks/useApi";

const WEEKS = 14; // ~98 days, GitHub-contributions style
const DAYS = WEEKS * 7;

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

function cellColor(run) {
  if (!run) return "var(--panel-2)"; // no run that day
  if (run.rainfall_available === false) return "var(--amber)"; // ran, terrain-only
  return "var(--moss)"; // ran with real rainfall data
}

function cellTitle(dateStr, run) {
  if (!run) return `${dateStr} — no run`;
  const pct = run.max_risk_probability != null ? Math.round(run.max_risk_probability * 100) : null;
  const parts = [
    dateStr,
    pct != null ? `peak risk ${pct}%` : null,
    `${run.alerts_triggered ?? 0} alert(s)`,
    run.rainfall_available === false ? "rainfall unavailable — terrain only" : "rainfall data OK",
  ].filter(Boolean);
  return parts.join(" · ");
}

export default function RunHeatmap({ refreshKey }) {
  const { data, loading } = useApi(`/api/pipeline-runs?limit=${DAYS}`, [refreshKey]);
  const runs = data?.runs || [];
  const byDate = Object.fromEntries(runs.map((r) => [r.run_date, r]));

  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  const cells = [];
  for (let i = DAYS - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - i);
    const dateStr = isoDate(d);
    cells.push({ dateStr, run: byDate[dateStr] });
  }
  // Pad to a full week grid, oldest-first, columns = weeks
  const leadingPad = (7 - (cells.length % 7)) % 7;
  const padded = Array(leadingPad).fill(null).concat(cells);
  const weeks = [];
  for (let i = 0; i < padded.length; i += 7) weeks.push(padded.slice(i, i + 7));

  const ranCount = runs.length;
  const terrainOnlyCount = runs.filter((r) => r.rainfall_available === false).length;

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
        <span style={{ fontSize: 12, color: "var(--chalk-dim)" }}>
          {loading ? "Loading run history…" : `${ranCount} runs in the last ${WEEKS} weeks${terrainOnlyCount ? ` · ${terrainOnlyCount} on terrain-only data` : ""}`}
        </span>
        <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--chalk-dim)" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: "var(--moss)", display: "inline-block" }} /> Ran, rainfall OK
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: "var(--amber)", display: "inline-block" }} /> Ran, terrain-only
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: "var(--panel-2)", border: "1px solid var(--line-strong)", display: "inline-block" }} /> No run
          </span>
        </div>
      </div>
      <div style={{ display: "flex", gap: 3, overflowX: "auto", paddingBottom: 4 }}>
        {weeks.map((week, wi) => (
          <div key={wi} style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {week.map((cell, di) => (
              <div
                key={di}
                title={cell ? cellTitle(cell.dateStr, cell.run) : ""}
                style={{
                  width: 12, height: 12, borderRadius: 2,
                  background: cell ? cellColor(cell.run) : "transparent",
                  border: cell && !cell.run ? "1px solid var(--line-strong)" : "none",
                  cursor: cell ? "default" : undefined,
                }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
