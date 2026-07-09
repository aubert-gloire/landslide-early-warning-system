import { useState } from 'react';

export function formatAlertMessage(unit) {
  const { unit_id, district, risk_probability, coordinates, top_feature } = unit;
  const pct = Math.round(risk_probability * 100);
  const [lng, lat] = coordinates;
  const mapsLink = `https://maps.google.com/?q=${lat},${lng}`;
  return (
    `LANDSLIDE ALERT ${district.toUpperCase()} ${unit_id}\n` +
    `Risk: ${pct}% (threshold 80%)\n` +
    `Driver: ${top_feature}\n` +
    `Location: ${mapsLink}\n` +
    `Reply Y to confirm on ground, N if false alarm.`
  );
}

export default function AlertPreview({ unit }) {
  const [copied, setCopied] = useState(false);
  const message = formatAlertMessage(unit);

  return (
    <div style={{
      width: 260, background: 'var(--panel)',
      border: '1px solid var(--line-strong)', borderRadius: 20,
      padding: '18px 16px', color: 'var(--chalk)',
      fontFamily: "'Public Sans', sans-serif",
    }}>
      <div style={{
        fontSize: 11, color: 'var(--chalk-dim)', marginBottom: 8,
        fontFamily: "'Space Mono', monospace",
      }}>
        SMS preview — Africa's Talking
      </div>
      <div style={{
        background: 'var(--terminal)', borderRadius: 12, padding: '12px 14px',
        fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap',
        fontFamily: "'Space Mono', monospace",
      }}>
        {message}
      </div>
      <button
        onClick={() => {
          navigator.clipboard.writeText(message);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
        style={{
          marginTop: 10, width: '100%', padding: '8px 0', borderRadius: 8,
          border: '1px solid var(--line-strong)', background: 'transparent',
          color: 'var(--chalk)', fontSize: 12, cursor: 'pointer',
        }}
      >
        {copied ? 'Copied' : 'Copy message'}
      </button>
    </div>
  );
}
