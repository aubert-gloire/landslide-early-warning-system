import { useApi } from "../hooks/useApi";

const LEVELS = [
  { key: "critical", label: "Critical", color: "var(--ember)" },
  { key: "high",     label: "High",     color: "var(--ember)" },
  { key: "medium",   label: "Elevated", color: "var(--amber)" },
  { key: "low",      label: "Normal",   color: "var(--moss)" },
];

export default function SeverityStrip({ refreshKey }) {
  const { data } = useApi("/api/risk-map", [refreshKey]);
  const features = data?.features || [];

  if (!features.length) {
    return <span style={{ fontSize: 11, color: "var(--chalk-dim)" }}>No assessment run yet</span>;
  }

  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const f of features) {
    const lvl = f.properties?.risk_level;
    if (counts[lvl] !== undefined) counts[lvl] += 1;
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
      {LEVELS.map(({ key, label, color }) => (
        <span key={key} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, display: "inline-block" }} />
          <strong style={{ color: "var(--chalk)" }}>{counts[key]}</strong>
          <span style={{ color: "var(--chalk-dim)" }}>{label}</span>
        </span>
      ))}
    </div>
  );
}
