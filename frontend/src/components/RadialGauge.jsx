const LEVEL_COLOR = {
  critical: "var(--ember)",
  high: "var(--ember)",
  medium: "var(--amber)",
  elevated: "var(--amber)",
  low: "var(--moss)",
  normal: "var(--moss)",
};

export default function RadialGauge({ value, level = "low", label, size = 96, stroke = 8 }) {
  const pct = Math.max(0, Math.min(100, value));
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - pct / 100);
  const color = LEVEL_COLOR[level] || "var(--storm)";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke="var(--line-strong)" strokeWidth={stroke}
          />
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke={color} strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset .5s ease, stroke .3s ease" }}
          />
        </svg>
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: size * 0.24, fontWeight: 700, color: "var(--chalk)",
        }}>
          {Math.round(pct)}%
        </div>
      </div>
      {label && (
        <div style={{ fontSize: 11, color: "var(--chalk-dim)", textAlign: "center" }}>{label}</div>
      )}
    </div>
  );
}
