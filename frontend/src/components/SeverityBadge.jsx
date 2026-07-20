// Colored pill + icon — one shared severity/status language used across
// alert levels, delivery status, officer feedback, and data-quality flags.
const PRESETS = {
  EMERGENCY:    { bg: "rgba(194,75,58,0.15)",  border: "rgba(194,75,58,0.4)",  text: "var(--ember-text)", icon: "▲" },
  WARNING:      { bg: "rgba(201,154,62,0.15)", border: "rgba(201,154,62,0.4)", text: "var(--amber-text)", icon: "▲" },
  WATCH:        { bg: "rgba(108,154,181,0.15)",border: "rgba(108,154,181,0.4)",text: "var(--storm-text)", icon: "●" },
  NORMAL:       { bg: "rgba(116,147,106,0.15)",border: "rgba(116,147,106,0.4)",text: "var(--moss-text)",  icon: "●" },
  TERRAIN_ONLY: { bg: "rgba(201,154,62,0.12)", border: "rgba(201,154,62,0.35)",text: "var(--amber-text)", icon: "◐" },
  SENT:         { bg: "rgba(116,147,106,0.12)",border: "rgba(116,147,106,0.3)",text: "var(--moss-text)",  icon: "✓" },
  DELIVERED:    { bg: "rgba(116,147,106,0.20)",border: "rgba(116,147,106,0.35)",text: "var(--moss-text)", icon: "✓" },
  PENDING:      { bg: "var(--panel-2)",        border: "var(--line-strong)",   text: "var(--chalk-dim)", icon: "○" },
  FAILED:       { bg: "rgba(194,75,58,0.15)",  border: "rgba(194,75,58,0.4)",  text: "var(--ember-text)", icon: "✕" },
  CONFIRMED:    { bg: "rgba(108,154,181,0.15)",border: "rgba(108,154,181,0.4)",text: "var(--storm-text)", icon: "✓" },
  DENIED:       { bg: "rgba(194,75,58,0.12)",  border: "rgba(194,75,58,0.35)", text: "var(--ember-text)", icon: "✕" },
};

export default function SeverityBadge({ level, label, size = "sm" }) {
  const preset = PRESETS[level] || PRESETS.PENDING;
  const fontSize = size === "sm" ? 10 : 11;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      fontSize, fontWeight: 700, letterSpacing: "0.05em",
      padding: size === "sm" ? "2px 9px" : "3px 11px", borderRadius: 999,
      background: preset.bg, border: `1px solid ${preset.border}`, color: preset.text,
      whiteSpace: "nowrap",
    }}>
      <span aria-hidden="true" style={{ fontSize: fontSize - 1 }}>{preset.icon}</span>
      {label ?? level}
    </span>
  );
}
