// Icon + big value + a min→max range bar with the current reading marked
// on it. Pattern borrowed from numeric-weather-style dashboards — works for
// any "where does today's value sit in its expected range" metric.
export default function RangeSliderTile({ icon, label, value, unit, min, max, minLabel, maxLabel, color = "var(--storm)" }) {
  const hasRange = min != null && max != null && max > min;
  const pct = hasRange ? Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100)) : 50;

  return (
    <div style={{
      background: "var(--panel)", border: "1px solid var(--line)",
      borderRadius: 14, padding: "16px 18px", flex: 1, minWidth: 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontSize: 12, color: "var(--chalk-dim)" }}>{label}</span>
      </div>

      <div style={{ fontFamily: "'Space Mono', monospace", fontSize: 26, fontWeight: 700, marginBottom: 12 }}>
        {value != null ? Math.round(value * 10) / 10 : "—"}
        <span style={{ fontSize: 14, color: "var(--chalk-dim)", marginLeft: 2 }}>{unit}</span>
      </div>

      <div style={{ position: "relative", height: 4, borderRadius: 2, background: "var(--line-strong)" }}>
        <div style={{
          position: "absolute", top: "50%", left: `${pct}%`, transform: "translate(-50%, -50%)",
          width: 10, height: 10, borderRadius: "50%", background: color,
          border: "2px solid var(--panel)", boxShadow: "0 0 0 1px " + color,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 10.5, color: "var(--chalk-dim)" }}>
        <span>{minLabel ?? (min != null ? `${min}${unit}` : "—")}</span>
        <span>{maxLabel ?? (max != null ? `${max}${unit}` : "—")}</span>
      </div>
    </div>
  );
}
