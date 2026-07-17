import { useApi } from "../hooks/useApi";

const DISTRICT_ACCENT = {
  Gakenke: { color: "var(--storm)",       text: "var(--storm-text)"  },
  Burera:  { color: "var(--moss)",        text: "var(--moss-text)"   },
  Musanze: { color: "var(--amber)",       text: "var(--amber-text)"  },
  Gicumbi: { color: "var(--ember)",       text: "var(--ember-text)"  },
};

function riskColor(p) {
  if (p == null)  return "var(--chalk-dim)";
  if (p >= 0.80)  return "var(--ember-text)";
  if (p >= 0.40)  return "var(--amber-text)";
  return "var(--moss-text)";
}

function alertBadge(level) {
  if (!level) return null;
  const colors = {
    EMERGENCY: { bg: "rgba(194,75,58,0.15)",  border: "rgba(194,75,58,0.4)",  text: "var(--ember-text)" },
    WARNING:   { bg: "rgba(201,154,62,0.15)", border: "rgba(201,154,62,0.4)", text: "var(--amber-text)" },
    WATCH:     { bg: "rgba(108,154,181,0.15)",border: "rgba(108,154,181,0.4)",text: "var(--storm-text)" },
  };
  const c = colors[level] || colors.WATCH;
  return (
    <span style={{
      fontSize: 10, fontFamily: "'Space Mono', monospace", letterSpacing: "0.06em",
      padding: "2px 8px", borderRadius: 999,
      background: c.bg, border: `1px solid ${c.border}`, color: c.text,
    }}>{level}</span>
  );
}

function DialGauge({ prob, district, sub }) {
  const rotation = prob != null ? -90 + prob * 180 : -90;
  const pct = prob != null ? `${Math.round(prob * 100)}%` : "—";
  const valueColor = riskColor(prob);

  return (
    <div style={{
      background: "var(--panel)", border: "1px solid var(--line)",
      borderRadius: 14, padding: "20px 16px 18px", textAlign: "center",
    }}>
      <svg viewBox="0 0 200 110" width="140" height="82" style={{ display: "block", margin: "0 auto" }}>
        <path d="M20 100 A80 80 0 0 1 100 20" fill="none" stroke="var(--moss)"  strokeWidth="12" strokeLinecap="round"/>
        <path d="M100 20 A80 80 0 0 1 156 44"  fill="none" stroke="var(--amber)" strokeWidth="12" strokeLinecap="round"/>
        <path d="M156 44 A80 80 0 0 1 180 100" fill="none" stroke="var(--ember)" strokeWidth="12" strokeLinecap="round"/>
        <g transform={`rotate(${rotation}, 100, 100)`}>
          <line x1="100" y1="100" x2="100" y2="28" stroke="var(--chalk)" strokeWidth="2.5"/>
          <circle cx="100" cy="100" r="5" fill="var(--chalk)"/>
        </g>
      </svg>
      <div style={{
        fontFamily: "'Space Mono', monospace", fontSize: 26, fontWeight: 700,
        color: valueColor, margin: "6px 0 2px",
      }}>{pct}</div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{district}</div>
      <div style={{ fontSize: 11.5, color: "var(--chalk-dim)" }}>{sub}</div>
    </div>
  );
}

function RainGauge({ mm, label, maxMm = 200 }) {
  const fill = Math.min(mm / maxMm, 1);
  const thresholdPct = (100 / maxMm) * 100;
  const fillColor = mm >= 100 ? "var(--ember)" : mm >= 60 ? "var(--amber)" : "var(--moss)";

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", height: "100%" }}>
      <div style={{
        position: "relative", width: 34, height: 150,
        border: "1px solid var(--line-strong)", borderRadius: 6,
        background: "var(--panel-2)", overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", left: -6, right: -6,
          bottom: `${thresholdPct}%`, borderTop: "1px dashed var(--chalk-dim)",
        }} />
        <div style={{
          position: "absolute", bottom: 0, left: 0, right: 0,
          height: `${fill * 100}%`, background: fillColor, borderRadius: "0 0 5px 5px",
          transition: "height 1s ease",
        }} />
      </div>
      <div style={{ fontFamily: "'Space Mono', monospace", fontSize: 12, marginTop: 8 }}>
        {mm > 0 ? `${mm}mm` : "—"}
      </div>
      <div style={{ fontSize: 11, color: "var(--chalk-dim)", marginTop: 2 }}>{label}</div>
    </div>
  );
}

export default function Dashboard({ onRunPipeline, onNavigate }) {
  const { data: distData, loading: dLoading } = useApi("/api/districts");
  const { data: alertData }                    = useApi("/api/alerts?limit=6");
  const { data: statsData }                    = useApi("/api/alerts/stats");

  const districts = distData?.districts ?? [];
  const alerts    = alertData?.alerts   ?? [];
  const stats     = statsData ?? {};
  const rainfallAvailable = distData?.rainfall_available;

  const alerting = districts.filter(d => d.alert_level === "EMERGENCY" || d.alert_level === "WARNING");
  const latestDate = districts[0]?.last_update;

  // Build hero headline
  let headline, subline;
  if (dLoading) {
    headline = "Loading today's assessment…";
    subline  = "";
  } else if (alerting.length === 0) {
    headline = "All districts within safe range this assessment.";
    subline  = rainfallAvailable === false
      ? "No rainfall data was captured for this assessment — weather looks clear, and scoring fell back to terrain signal only. Antecedent rainfall could not be factored in."
      : "No slope units have crossed the alert threshold. Continue monitoring antecedent rainfall conditions.";
  } else if (alerting.length === 1) {
    headline = `${alerting[0].district} is crossing the alert threshold.`;
    subline  = `${alerting[0].district} has exceeded ${Math.round(alerting[0].highest_risk_probability * 100)}% predicted risk. Five-day antecedent rainfall is the primary driver. SMS alerts have been dispatched to district officers.`;
    if (rainfallAvailable === false) {
      subline += " NOTE: rainfall data was unavailable for this run — this assessment is based on terrain signal only.";
    }
  } else {
    const names = alerting.map(d => d.district).join(" and ");
    headline = `${names} are crossing the alert threshold.`;
    subline  = `${alerting.length} districts have exceeded 80% predicted risk following antecedent rainfall accumulation — the strongest signal in this model. SMS alerts have been dispatched to district officers.`;
    if (rainfallAvailable === false) {
      subline += " NOTE: rainfall data was unavailable for this run — this assessment is based on terrain signal only.";
    }
  }

  // Top features from highest-risk district
  const topDistrict = [...districts].sort((a, b) => (b.highest_risk_probability ?? 0) - (a.highest_risk_probability ?? 0))[0];
  const topFeatures = topDistrict?.top_features ?? [];

  const FEATURE_LABELS = {
    antecedent_5day_mm:       "5-day rainfall sum",
    slope_angle:              "Slope angle",
    daily_mm:                 "Daily rainfall intensity",
    twi:                      "Topographic wetness (TWI)",
    ndvi:                     "Vegetation cover (NDVI)",
    drainage_density:         "Drainage density",
    antecedent_3day_mm:       "3-day antecedent rain",
    antecedent_10day_mm:      "10-day antecedent rain",
    rainfall_intensity_ratio: "Rainfall intensity ratio",
    soil_class:               "Soil class",
    landuse_class:            "Land use class",
  };

  return (
    <div>

      {/* ── Hero ── */}
      <section style={{ paddingBottom: 36, borderBottom: "1px solid var(--line)", marginBottom: 36 }}>
        <p style={{
          fontFamily: "'Space Mono', monospace", fontSize: 11, color: "var(--ember-text)",
          letterSpacing: "0.08em", margin: "0 0 14px",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <span style={{ width: 16, height: 1, background: "var(--ember-text)", display: "inline-block" }} />
          {latestDate
            ? `Assessment date — ${new Date(latestDate).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}`
            : "Northern Province Landslide Watch"
          }
          {rainfallAvailable === false && (
            <span style={{
              fontSize: 10, letterSpacing: "0.05em", padding: "2px 8px", borderRadius: 999,
              background: "rgba(201,154,62,0.12)", border: "1px solid rgba(201,154,62,0.35)",
              color: "var(--amber-text)",
            }}>TERRAIN-ONLY — NO RAINFALL DATA</span>
          )}
        </p>
        <h2 style={{
          fontFamily: "'Space Mono', monospace", fontWeight: 700,
          fontSize: "clamp(22px, 3.2vw, 34px)", lineHeight: 1.2,
          margin: "0 0 14px", maxWidth: 780, color: "var(--chalk)",
        }}>{headline}</h2>
        {subline && (
          <p style={{ color: "var(--chalk-dim)", maxWidth: 560, margin: "0 0 24px", fontSize: 14 }}>
            {subline}
          </p>
        )}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            onClick={() => onNavigate?.("Predict")}
            style={{
              borderRadius: 10, padding: "10px 18px", fontSize: 13, fontWeight: 600,
              background: "var(--ember)", border: "1px solid var(--ember)", color: "#fff",
              display: "inline-flex", alignItems: "center", gap: 8,
            }}
          >
            Run manual prediction
          </button>
          <button
            onClick={onRunPipeline}
            title="Fetch today's satellite rainfall and re-score all 396 slope units now, instead of waiting for the next scheduled run"
            style={{
              borderRadius: 10, padding: "10px 18px", fontSize: 13, fontWeight: 600,
              background: "transparent", border: "1px solid var(--line-strong)", color: "var(--chalk)",
              display: "inline-flex", alignItems: "center", gap: 8,
            }}
          >
            Run today's prediction
          </button>
          <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
            {stats.total_alerts > 0 && (
              <>
                <span style={{ fontSize: 12, color: "var(--chalk-dim)" }}>
                  <span style={{ color: "var(--chalk)", fontWeight: 600 }}>{stats.total_alerts}</span> total alerts
                </span>
                <span style={{ fontSize: 12, color: "var(--chalk-dim)" }}>
                  <span style={{ color: "var(--moss-text)", fontWeight: 600 }}>{stats.confirmed}</span> confirmed
                </span>
                <span style={{ fontSize: 12, color: "var(--chalk-dim)" }}>
                  <span style={{ color: "var(--amber-text)", fontWeight: 600 }}>{stats.awaiting_feedback}</span> awaiting reply
                </span>
              </>
            )}
          </div>
        </div>
      </section>

      {/* ── District Dials ── */}
      <section style={{ marginBottom: 36 }}>
        <p style={{
          fontFamily: "'Space Mono', monospace", fontSize: 11, color: "var(--chalk-dim)",
          letterSpacing: "0.08em", textTransform: "uppercase", margin: "0 0 20px",
        }}>District risk — today</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
          {dLoading
            ? [1,2,3,4].map(i => (
                <div key={i} style={{
                  background: "var(--panel)", border: "1px solid var(--line)",
                  borderRadius: 14, padding: "20px 16px 18px", height: 170,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <span style={{ color: "var(--chalk-dim)", fontSize: 12 }}>Loading…</span>
                </div>
              ))
            : districts.map(d => (
                <div key={d.district}>
                  <DialGauge
                    prob={d.highest_risk_probability}
                    district={d.district}
                    sub={d.avg_5day_mm > 0
                      ? `${d.avg_5day_mm}mm 5-day rain`
                      : `${d.unit_count} slope units`}
                  />
                  {d.alert_level && (
                    <div style={{ textAlign: "center", marginTop: 6 }}>
                      {alertBadge(d.alert_level)}
                    </div>
                  )}
                </div>
              ))
          }
        </div>
      </section>

      {/* ── Split: Rainfall + Explainability ── */}
      <section style={{
        display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 20,
        marginBottom: 36, paddingBottom: 36, borderBottom: "1px solid var(--line)",
      }}>

        {/* Rainfall gauges */}
        <div style={{
          background: "var(--panel)", border: "1px solid var(--line)",
          borderRadius: 14, padding: 20,
        }}>
          <p style={{ fontSize: 13, fontWeight: 600, margin: "0 0 2px" }}>5-day rainfall gauge</p>
          <p style={{ fontSize: 11.5, color: "var(--chalk-dim)", margin: "0 0 16px" }}>
            Dashed line marks 100mm alert threshold
          </p>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 16, height: 190, padding: "0 4px 4px" }}>
            {districts.length > 0
              ? districts.map(d => (
                  <RainGauge
                    key={d.district}
                    mm={d.avg_5day_mm ?? 0}
                    label={d.district.slice(0, 2).toUpperCase()}
                  />
                ))
              : [1,2,3,4].map(i => <RainGauge key={i} mm={0} label="—" />)
            }
          </div>
        </div>

        {/* Feature explainability */}
        <div style={{
          background: "var(--panel)", border: "1px solid var(--line)",
          borderRadius: 14, padding: 20,
        }}>
          <p style={{ fontSize: 13, fontWeight: 600, margin: "0 0 2px" }}>Why this alert triggered</p>
          <p style={{ fontSize: 11.5, color: "var(--chalk-dim)", margin: "0 0 18px" }}>
            Feature contribution — highest-risk unit
            {topDistrict && ` · ${topDistrict.district}`}
          </p>
          {topFeatures.length > 0 ? (
            topFeatures.slice(0, 6).map(([name, imp]) => (
              <div key={name} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <span style={{
                  fontFamily: "'Space Mono', monospace", fontSize: 11,
                  color: "var(--chalk-dim)", width: 180, flexShrink: 0,
                }}>
                  {FEATURE_LABELS[name] ?? name.replace(/_/g, " ")}
                </span>
                <div style={{
                  flex: 1, height: 6, background: "var(--panel-2)",
                  borderRadius: 3, position: "relative",
                }}>
                  <div style={{
                    height: 6, borderRadius: 3, background: "var(--storm)",
                    width: `${imp * 100}%`, transition: "width 0.6s ease",
                  }} />
                </div>
                <span style={{
                  fontFamily: "'Space Mono', monospace", fontSize: 11,
                  width: 36, textAlign: "right", flexShrink: 0,
                }}>
                  {Math.round(imp * 100)}%
                </span>
              </div>
            ))
          ) : (
            <p style={{ color: "var(--chalk-dim)", fontSize: 12 }}>
              No prediction data yet — run the pipeline to populate.
            </p>
          )}
        </div>
      </section>

      {/* ── Terminal dispatch log ── */}
      <section style={{ marginBottom: 8 }}>
        <p style={{
          fontFamily: "'Space Mono', monospace", fontSize: 11, color: "var(--chalk-dim)",
          letterSpacing: "0.08em", textTransform: "uppercase", margin: "0 0 14px",
        }}>Dispatch log</p>
        <div style={{
          background: "var(--terminal)", border: "1px solid var(--line)",
          borderRadius: 10, padding: "14px 16px",
          fontFamily: "'Space Mono', monospace", fontSize: 12,
          overflowX: "auto",
        }}>
          {alerts.length === 0 ? (
            <div style={{ color: "var(--chalk-dim)", padding: "6px 0" }}>No alerts dispatched yet.</div>
          ) : alerts.map((a, i) => {
            const ts = a.sent_at
              ? new Date(a.sent_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
              : "—";
            const dateStr = a.sent_at
              ? new Date(a.sent_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })
              : "";
            const prob = a.risk_probability != null ? a.risk_probability.toFixed(2) : "—";
            const probColor = a.risk_probability >= 0.8
              ? "var(--ember-text)" : a.risk_probability >= 0.6
              ? "var(--amber-text)" : "var(--moss-text)";
            const ackColor = a.feedback === "CONFIRMED"
              ? "var(--moss-text)" : a.feedback === "DENIED"
              ? "var(--ember-text)" : "var(--amber-text)";
            const ackLabel = a.feedback === "CONFIRMED"
              ? "confirmed" : a.feedback === "DENIED"
              ? "denied" : "pending";
            const status = a.delivery_status === "sent" ? "sent" : "failed";
            const statusColor = a.delivery_status === "sent" ? "var(--chalk-dim)" : "var(--ember-text)";

            return (
              <div key={a.alert_id ?? i} style={{
                whiteSpace: "pre", padding: "5px 0",
                borderBottom: i < alerts.length - 1 ? "1px solid rgba(237,237,230,0.06)" : "none",
                display: "flex", gap: 0, flexWrap: "nowrap",
              }}>
                <span style={{ color: "var(--chalk-dim)" }}>{dateStr} {ts}  </span>
                <span style={{ color: "var(--chalk)", minWidth: 80 }}>
                  {(a.district ?? "").padEnd(9)}
                </span>
                <span style={{ color: "var(--chalk-dim)" }}>  risk=</span>
                <span style={{ color: probColor }}>{prob}</span>
                <span style={{ color: "var(--chalk-dim)" }}>  sms=</span>
                <span style={{ color: statusColor }}>{status}</span>
                <span style={{ color: "var(--chalk-dim)" }}>  ack=</span>
                <span style={{ color: ackColor }}>{ackLabel}</span>
              </div>
            );
          })}
        </div>
      </section>

    </div>
  );
}
