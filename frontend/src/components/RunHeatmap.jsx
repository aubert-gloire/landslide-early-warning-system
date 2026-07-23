import { useApi } from "../hooks/useApi";

const WEEKS = 14; // ~98 days
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

const LEGEND_STYLE = {
  wrap: { display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 },
  count: { fontFamily: "'Space Mono', monospace", fontSize: 15, fontWeight: 700 },
  label: { fontSize: 10.5, color: "var(--chalk-dim)", display: "flex", alignItems: "center", gap: 5 },
};

function LegendStat({ count, dotColor, label, dotOutline }) {
  return (
    <div style={LEGEND_STYLE.wrap}>
      <span style={LEGEND_STYLE.count}>{count}</span>
      <span style={LEGEND_STYLE.label}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%", background: dotColor, display: "inline-block",
          border: dotOutline ? "1px solid var(--line-strong)" : "none",
        }} />
        {label}
      </span>
    </div>
  );
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
  const rainfallOkCount = runs.filter((r) => r.rainfall_available !== false).length;
  const terrainOnlyCount = runs.filter((r) => r.rainfall_available === false).length;

  // The pipeline hasn't necessarily existed for the full 98-day window —
  // measure coverage against days since its first recorded run instead,
  // so a young system doesn't read as an (inaccurate) reliability problem.
  const firstRunDate = runs.map((r) => r.run_date).sort()[0];
  let eligibleDays = DAYS;
  if (firstRunDate) {
    const firstDate = new Date(`${firstRunDate}T00:00:00Z`);
    const daysSinceStart = Math.floor((today - firstDate) / 86400000) + 1;
    eligibleDays = Math.min(DAYS, Math.max(1, daysSinceStart));
  }
  const sinceLaunch = eligibleDays < DAYS;
  const noRunCount = Math.max(0, eligibleDays - ranCount);
  const coveragePct = Math.round((ranCount / eligibleDays) * 1000) / 10;

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18, flexWrap: "wrap", gap: 16 }}>
        <div>
          <div style={{ fontSize: 11, color: "var(--chalk-dim)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            {sinceLaunch ? `Run coverage — since launch (${eligibleDays}d)` : `Run coverage — last ${WEEKS} weeks`}
          </div>
          <div style={{ fontFamily: "'Space Mono', monospace", fontSize: 30, fontWeight: 700 }}>
            {loading ? "…" : `${coveragePct}%`}
          </div>
        </div>
        <div style={{ display: "flex", gap: 22 }}>
          <LegendStat count={rainfallOkCount} dotColor="var(--moss)" label="Rainfall OK" />
          <LegendStat count={terrainOnlyCount} dotColor="var(--amber)" label="Terrain-only" />
          <LegendStat count={noRunCount} dotColor="var(--panel-2)" dotOutline label="No run" />
        </div>
      </div>

      <div style={{ display: "flex", gap: 4, overflowX: "auto", paddingBottom: 4 }}>
        {weeks.map((week, wi) => (
          <div key={wi} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {week.map((cell, di) => (
              <div
                key={di}
                title={cell ? cellTitle(cell.dateStr, cell.run) : ""}
                style={{
                  width: 10, height: 10, borderRadius: "50%",
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
