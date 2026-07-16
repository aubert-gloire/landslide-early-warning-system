export default function ThresholdSlider({ label, value, warn, critical, max, unit = "", invert = false }) {
  const hi = max ?? critical * 1.4;
  const pct = Math.max(0, Math.min(100, (value / hi) * 100));
  const warnPct = Math.max(0, Math.min(100, (warn / hi) * 100));
  const criticalPct = Math.max(0, Math.min(100, (critical / hi) * 100));

  const gradient = invert
    ? "linear-gradient(90deg, var(--ember) 0%, var(--amber) 55%, var(--moss) 100%)"
    : "linear-gradient(90deg, var(--moss) 0%, var(--amber) 55%, var(--ember) 100%)";

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span style={{ fontSize: 12, color: "var(--chalk-dim)" }}>{label}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--chalk)" }}>{value}{unit}</span>
      </div>
      <div style={{ position: "relative", height: 6, borderRadius: 3, background: gradient, opacity: 0.85 }}>
        <div style={{
          position: "absolute", top: -3, left: `${criticalPct}%`,
          width: 1, height: 12, background: "var(--chalk-dim)", opacity: 0.5,
        }} />
        <div style={{
          position: "absolute", top: -4, left: `calc(${pct}% - 5px)`,
          width: 10, height: 10, borderRadius: "50%",
          background: "var(--chalk)", border: "2px solid var(--panel)",
          boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 3 }}>
        <span style={{ fontSize: 10, color: "var(--chalk-dim)" }}>0{unit}</span>
        <span style={{ fontSize: 10, color: "var(--chalk-dim)" }}>critical {critical}{unit}</span>
      </div>
    </div>
  );
}
