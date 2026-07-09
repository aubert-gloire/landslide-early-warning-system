import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

const RISK_COLORS = {
  critical: { bg: "rgba(194,75,58,0.15)",  text: "var(--ember-text)", border: "rgba(194,75,58,0.4)" },
  high:     { bg: "rgba(201,154,62,0.12)", text: "var(--amber-text)", border: "rgba(201,154,62,0.35)" },
  medium:   { bg: "rgba(201,154,62,0.08)", text: "var(--amber-text)", border: "rgba(201,154,62,0.25)" },
  low:      { bg: "rgba(116,147,106,0.12)", text: "var(--moss-text)", border: "rgba(116,147,106,0.35)" },
};
const THRESHOLD_COLORS = {
  critical:     "var(--ember-text)",
  elevated:     "var(--amber-text)",
  normal:       "var(--moss-text)",
  no_threshold: "var(--chalk-dim)",
  no_value:     "var(--chalk-dim)",
};

const FIELD_META = {
  slope_angle:             { label: "Slope Angle (°)",           placeholder: "e.g. 38.5",  min: 0,    max: 90,   step: 0.5,  required: true,  hint: "0–90°. Critical risk above 35°." },
  daily_mm:                { label: "Daily Rainfall (mm)",       placeholder: "e.g. 62",    min: 0,    max: 600,  step: 1,    required: true,  hint: "24h rainfall. Critical above 50mm." },
  antecedent_3day_mm:      { label: "3-day Antecedent (mm)",     placeholder: "e.g. 95",    min: 0,    max: 600,  step: 1,    required: true,  hint: "Cumulative prior 3 days — shallow soil saturation." },
  antecedent_5day_mm:      { label: "5-day Antecedent (mm)",     placeholder: "e.g. 175",   min: 0,    max: 2000, step: 1,    required: true,  hint: "Cumulative prior 5 days. Critical above 150mm." },
  antecedent_10day_mm:     { label: "10-day Antecedent (mm)",    placeholder: "e.g. 220",   min: 0,    max: 3000, step: 1,    required: false, hint: "Cumulative prior 10 days — deep clay saturation." },
  aspect:                  { label: "Slope Aspect (°)",           placeholder: "e.g. 225",   min: 0,    max: 360,  step: 1,    required: false, hint: "0=N 90=E 180=S 270=W. Optional." },
  twi:                     { label: "TWI",                        placeholder: "e.g. 9.3",   min: 0,    max: 30,   step: 0.1,  required: false, hint: "Topographic Wetness Index. Critical above 12." },
  drainage_density:        { label: "Drainage Density (km/km²)",  placeholder: "e.g. 2.8",  min: 0,    max: 20,   step: 0.1,  required: false, hint: "Stream network density. Optional." },
  ndvi:                    { label: "NDVI",                       placeholder: "e.g. 0.42",  min: -1,   max: 1,    step: 0.01, required: false, hint: "-1 to 1. Low (<0.35) = sparse vegetation." },
  soil_class:              { label: "Soil Class (1–10)",          placeholder: "e.g. 5",     min: 1,    max: 10,   step: 1,    required: false, hint: "SoilGrids class. Class 5 = clay-rich." },
};

const SCENARIO_PRESETS = [
  {
    label: "High risk — steep + heavy rain",
    values: { slope_angle: 42, daily_mm: 78, antecedent_3day_mm: 118, antecedent_5day_mm: 210, antecedent_10day_mm: 285, twi: 13.2, ndvi: 0.28 },
  },
  {
    label: "Medium risk — moderate conditions",
    values: { slope_angle: 28, daily_mm: 35, antecedent_3day_mm: 52, antecedent_5day_mm: 95, antecedent_10day_mm: 130, twi: 7.5, ndvi: 0.55 },
  },
  {
    label: "Low risk — dry season baseline",
    values: { slope_angle: 15, daily_mm: 5, antecedent_3day_mm: 8, antecedent_5day_mm: 12, antecedent_10day_mm: 18, twi: 4.1, ndvi: 0.72 },
  },
  {
    label: "Invalid — negative rainfall",
    values: { slope_angle: 30, daily_mm: -20, antecedent_3day_mm: 40, antecedent_5day_mm: 80 },
  },
  {
    label: "Invalid — slope > 90°",
    values: { slope_angle: 110, daily_mm: 40, antecedent_3day_mm: 55, antecedent_5day_mm: 100 },
  },
];

const styles = {
  root: { display: "grid", gridTemplateColumns: "clamp(280px, 30%, 360px) 1fr", gap: 24, alignItems: "start" },
  panel: { background: "var(--panel)", border: "1px solid var(--line-strong)", borderRadius: 10, padding: 20 },
  sectionTitle: { fontSize: 12, fontWeight: 600, color: "var(--chalk-dim)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12 },
  fieldRow: { marginBottom: 14 },
  label: { display: "block", fontSize: 12, color: "var(--chalk-dim)", marginBottom: 4, fontWeight: 500 },
  input: {
    width: "100%", boxSizing: "border-box",
    background: "var(--panel-2)", border: "1px solid var(--line-strong)", color: "var(--chalk)",
    padding: "7px 10px", borderRadius: 6, fontSize: 13,
  },
  hint: { fontSize: 11, color: "var(--chalk-dim)", marginTop: 3 },
  errorInput: { borderColor: "var(--ember)" },
  btn: {
    width: "100%", padding: "10px 0", background: "var(--storm)",
    color: "#fff", border: "none", borderRadius: 6, fontSize: 14,
    fontWeight: 600, cursor: "pointer", marginTop: 8,
  },
  presetBtn: {
    display: "block", width: "100%", textAlign: "left",
    padding: "7px 10px", background: "var(--panel-2)", border: "1px solid var(--line-strong)",
    color: "var(--chalk-dim)", borderRadius: 6, fontSize: 12, cursor: "pointer",
    marginBottom: 6,
  },
  invalidPreset: { borderColor: "var(--ember)", color: "var(--ember-text)" },
  divider: { borderColor: "var(--line)", margin: "16px 0" },
  narrative: { lineHeight: 1.7, fontSize: 14, color: "var(--chalk)", marginBottom: 16 },
  featureRow: {
    display: "flex", alignItems: "flex-start", gap: 10,
    padding: "10px 0", borderBottom: "1px solid var(--line)",
  },
  rank: { fontSize: 18, fontWeight: 700, color: "var(--chalk-dim)", minWidth: 24, textAlign: "center" },
  featureName: { fontWeight: 600, fontSize: 13, color: "var(--chalk)" },
  featureValue: { fontSize: 12, color: "var(--chalk-dim)" },
  featureCtx: { fontSize: 12, marginTop: 2 },
  impBar: { height: 4, borderRadius: 2, background: "var(--storm)", marginTop: 6 },
  errorBox: { background: "rgba(194,75,58,0.12)", border: "1px solid rgba(194,75,58,0.35)", borderRadius: 8, padding: 16 },
  errorTitle: { color: "var(--ember-text)", fontWeight: 600, fontSize: 13, marginBottom: 8 },
  errorItem: { color: "var(--ember-text)", fontSize: 13, marginBottom: 4 },
  metricRow: { display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" },
  metric: { flex: 1, minWidth: 120, background: "var(--panel-2)", borderRadius: 8, padding: "12px 16px" },
  metricVal: { fontSize: 24, fontWeight: 700 },
  metricLabel: { fontSize: 11, color: "var(--chalk-dim)", marginTop: 2 },
};

function RiskBadge({ level }) {
  const c = RISK_COLORS[level] || RISK_COLORS.low;
  return (
    <span style={{
      display: "inline-block", padding: "3px 12px", borderRadius: 12,
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      fontWeight: 700, fontSize: 12, textTransform: "uppercase",
    }}>
      {level}
    </span>
  );
}

function defaultForm() {
  return Object.fromEntries(Object.keys(FIELD_META).map((k) => [k, ""]));
}

export default function PredictPanel() {
  const [form, setForm] = useState(defaultForm());
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [validationErrors, setValidationErrors] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [alertDistrict, setAlertDistrict] = useState("");
  const [alertLoading, setAlertLoading] = useState(false);
  const [alertResult, setAlertResult] = useState(null);

  function handleChange(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
    setFieldErrors((e) => ({ ...e, [field]: undefined }));
  }

  function applyPreset(preset) {
    const next = defaultForm();
    for (const [k, v] of Object.entries(preset.values)) {
      next[k] = String(v);
    }
    setForm(next);
    setResult(null);
    setValidationErrors(null);
    setFieldErrors({});
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setValidationErrors(null);
    setFieldErrors({});

    const body = {};
    for (const [k, meta] of Object.entries(FIELD_META)) {
      const raw = form[k].trim();
      if (raw === "") {
        if (meta.required) {
          setFieldErrors((err) => ({ ...err, [k]: "Required" }));
        }
        continue;
      }
      const num = k === "soil_class" ? parseInt(raw, 10) : parseFloat(raw);
      if (isNaN(num)) {
        setFieldErrors((err) => ({ ...err, [k]: "Must be a number" }));
        setLoading(false);
        return;
      }
      body[k] = num;
    }

    try {
      const res = await fetch(`${API_BASE}/api/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (res.status === 422) {
        const errData = await res.json();
        const errors = (errData.detail || []).map((d) => ({
          field: d.loc?.slice(1).join(".") || "input",
          message: d.msg,
          value: d.input,
        }));
        setValidationErrors(errors);
        return;
      }
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setValidationErrors([{ field: "server", message: errData.detail || `Server error ${res.status}` }]);
        return;
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setValidationErrors([{ field: "network", message: `Network error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSendAlert(force = false) {
    setAlertLoading(true);
    setAlertResult(null);
    const body = { district: alertDistrict, force };
    for (const [k] of Object.entries(FIELD_META)) {
      const raw = form[k].trim();
      if (raw === "") continue;
      body[k] = k === "soil_class" ? parseInt(raw, 10) : parseFloat(raw);
    }
    try {
      const res = await fetch(`${API_BASE}/api/predict/alert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setAlertResult({ error: data.detail || `Error ${res.status}` });
      } else {
        setAlertResult(data);
      }
    } catch (err) {
      setAlertResult({ error: `Network error: ${err.message}` });
    } finally {
      setAlertLoading(false);
    }
  }

  const riskColors = result ? RISK_COLORS[result.risk_level] || RISK_COLORS.low : null;

  return (
    <div style={styles.root}>
      {/* Left: input form */}
      <div>
        <div style={styles.panel}>
          <div style={styles.sectionTitle}>Scenario Presets</div>
          {SCENARIO_PRESETS.map((p) => {
            const isInvalid = p.label.startsWith("Invalid");
            return (
              <button
                key={p.label}
                style={{ ...styles.presetBtn, ...(isInvalid ? styles.invalidPreset : {}) }}
                onClick={() => applyPreset(p)}
              >
                {isInvalid ? "⚠ " : ""}{p.label}
              </button>
            );
          })}
        </div>

        <div style={{ ...styles.panel, marginTop: 16 }}>
          <div style={styles.sectionTitle}>Feature Inputs</div>
          <form onSubmit={handleSubmit}>
            {Object.entries(FIELD_META).map(([field, meta]) => (
              <div key={field} style={styles.fieldRow}>
                <label style={styles.label}>
                  {meta.label}
                  {meta.required && <span style={{ color: "var(--ember)" }}> *</span>}
                </label>
                <input
                  type="number"
                  step={meta.step}
                  min={meta.min}
                  max={meta.max}
                  placeholder={meta.placeholder}
                  value={form[field]}
                  onChange={(e) => handleChange(field, e.target.value)}
                  style={{
                    ...styles.input,
                    ...(fieldErrors[field] ? styles.errorInput : {}),
                  }}
                />
                {fieldErrors[field] && (
                  <div style={{ color: "var(--ember-text)", fontSize: 11, marginTop: 3 }}>{fieldErrors[field]}</div>
                )}
                <div style={styles.hint}>{meta.hint}</div>
              </div>
            ))}
            <button type="submit" style={styles.btn} disabled={loading}>
              {loading ? "Running model…" : "Run Prediction"}
            </button>
          </form>
        </div>
      </div>

      {/* Right: result */}
      <div>
        {!result && !validationErrors && (
          <div style={{ ...styles.panel, color: "var(--chalk-dim)", fontSize: 13, lineHeight: 1.8 }}>
            <strong style={{ color: "var(--chalk)" }}>How to use this panel</strong>
            <p style={{ marginTop: 8 }}>
              Select a preset scenario or enter feature values manually, then click <em>Run Prediction</em>.
            </p>
            <p>
              The model returns a risk probability, risk level, and a narrative explaining which features
              are driving the classification — with reference to the evidence-based thresholds from
              Kuradusenge et al. (2020).
            </p>
            <p>
              Try the two <span style={{ color: "var(--ember-text)" }}>invalid presets</span> to see how the API
              rejects physically impossible inputs (negative rainfall, slope &gt; 90°) with
              422 validation errors before the model even runs.
            </p>
          </div>
        )}

        {validationErrors && (
          <div style={styles.errorBox}>
            <div style={styles.errorTitle}>
              Input Validation Failed (HTTP 422 — Unprocessable Entity)
            </div>
            <p style={{ color: "var(--chalk-dim)", fontSize: 12, marginBottom: 12 }}>
              The API rejected the request before running the model. Fix the inputs below:
            </p>
            {validationErrors.map((err, i) => (
              <div key={i} style={styles.errorItem}>
                <strong>{err.field}:</strong> {err.message}
                {err.value !== undefined && (
                  <span style={{ color: "var(--chalk-dim)" }}> (got: {JSON.stringify(err.value)})</span>
                )}
              </div>
            ))}
            <p style={{ color: "var(--chalk-dim)", fontSize: 11, marginTop: 12, marginBottom: 0 }}>
              This demonstrates system robustness — invalid data is rejected at the API boundary,
              never reaching the model or database.
            </p>
          </div>
        )}

        {result && (
          <div>
            {/* Risk summary */}
            <div style={{ ...styles.panel, borderColor: riskColors.border, marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <RiskBadge level={result.risk_level} />
                <span style={{ color: "var(--chalk-dim)", fontSize: 12 }}>
                  Alert threshold: {Math.round(result.production_threshold * 100)}%
                </span>
                {result.alert_triggered && (
                  <span style={{ color: "var(--ember)", fontSize: 12, fontWeight: 600 }}>
                    ⚠ ALERT THRESHOLD EXCEEDED
                  </span>
                )}
              </div>

              <div style={styles.metricRow}>
                <div style={styles.metric}>
                  <div style={{ ...styles.metricVal, color: riskColors.text }}>
                    {result.risk_probability_pct}%
                  </div>
                  <div style={styles.metricLabel}>Risk Probability</div>
                </div>
                <div style={styles.metric}>
                  <div style={{ ...styles.metricVal, color: result.alert_triggered ? "var(--ember)" : "var(--moss-text)" }}>
                    {result.alert_triggered ? "YES" : "NO"}
                  </div>
                  <div style={styles.metricLabel}>Alert Triggered</div>
                </div>
                <div style={styles.metric}>
                  <div style={{ ...styles.metricVal, color: "var(--chalk-dim)", fontSize: 16 }}>
                    {result.input_summary.slope_angle}° / {result.input_summary.daily_mm}mm
                  </div>
                  <div style={styles.metricLabel}>Slope / Daily Rain</div>
                </div>
              </div>

              <div style={{ ...styles.sectionTitle, marginTop: 4 }}>Model Reasoning</div>
              <div style={styles.narrative}>{result.risk_narrative}</div>
            </div>

            {/* Expert SMS dispatch */}
            <div style={{ ...styles.panel, marginBottom: 16, borderColor: result.alert_triggered ? "var(--ember)" : "var(--line-strong)" }}>
              <div style={styles.sectionTitle}>Expert SMS Dispatch</div>
              <p style={{ fontSize: 12, color: "var(--chalk-dim)", marginBottom: 12, marginTop: 0 }}>
                Enter the district name and send an SMS alert directly to registered field officers.
                {!result.alert_triggered && " The model is below threshold — use Force Send to override."}
              </p>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
                <input
                  type="text"
                  placeholder="District (e.g. Musanze)"
                  value={alertDistrict}
                  onChange={(e) => { setAlertDistrict(e.target.value); setAlertResult(null); }}
                  style={{ ...styles.input, flex: 1, minWidth: 160 }}
                />
                <button
                  onClick={() => handleSendAlert(false)}
                  disabled={alertLoading || !alertDistrict.trim() || !result.alert_triggered}
                  style={{
                    ...styles.btn, width: "auto", padding: "8px 16px", marginTop: 0,
                    background: result.alert_triggered ? "var(--ember)" : "var(--panel-2)",
                    color: "#fff",
                    cursor: (alertLoading || !alertDistrict.trim() || !result.alert_triggered) ? "not-allowed" : "pointer",
                    opacity: (!alertDistrict.trim() || !result.alert_triggered) ? 0.5 : 1,
                  }}
                >
                  {alertLoading ? "Sending…" : "Send SMS Alert"}
                </button>
                <button
                  onClick={() => handleSendAlert(true)}
                  disabled={alertLoading || !alertDistrict.trim()}
                  style={{
                    ...styles.btn, width: "auto", padding: "8px 16px", marginTop: 0,
                    background: "rgba(201,154,62,0.15)",
                    border: "1px solid rgba(201,154,62,0.4)",
                    color: "var(--amber-text)",
                    cursor: (alertLoading || !alertDistrict.trim()) ? "not-allowed" : "pointer",
                    opacity: !alertDistrict.trim() ? 0.5 : 1,
                    fontSize: 12,
                  }}
                >
                  Force Send
                </button>
              </div>

              {alertResult && !alertResult.error && alertResult.sent && (
                <div style={{ marginTop: 12, background: "rgba(116,147,106,0.12)", border: "1px solid rgba(116,147,106,0.35)", borderRadius: 6, padding: 12 }}>
                  <div style={{ color: "var(--moss-text)", fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                    ✓ SMS sent to {alertResult.sms_count} recipient{alertResult.sms_count !== 1 ? "s" : ""} in {alertResult.district}
                    {alertResult.forced && <span style={{ color: "var(--amber-text)" }}> (expert override)</span>}
                  </div>
                  {alertResult.recipients.map((r) => (
                    <div key={r.alert_id} style={{ fontSize: 12, color: "var(--moss-text)" }}>
                      → {r.name} ({r.phone})
                    </div>
                  ))}
                </div>
              )}
              {alertResult && !alertResult.error && !alertResult.sent && (
                <div style={{ marginTop: 12, background: "var(--panel-2)", borderRadius: 6, padding: 10, fontSize: 12, color: "var(--chalk-dim)" }}>
                  {alertResult.reason}
                </div>
              )}
              {alertResult && alertResult.error && (
                <div style={{ marginTop: 12, background: "rgba(194,75,58,0.12)", borderRadius: 6, padding: 10, fontSize: 12, color: "var(--ember-text)" }}>
                  {alertResult.error}
                </div>
              )}
            </div>

            {/* Top features */}
            <div style={styles.panel}>
              <div style={styles.sectionTitle}>Top Contributing Features</div>
              {(() => {
                const maxImp = Math.max(...result.top_features.map((f) => f.importance), 0.001);
                return result.top_features.map((f, i) => (
                  <div key={f.feature} style={styles.featureRow}>
                    <div style={styles.rank}>{i + 1}</div>
                    <div style={{ flex: 1 }}>
                      <div style={styles.featureName}>{f.label}</div>
                      <div style={styles.featureValue}>
                        Value: <strong>{f.value ?? "N/A"}</strong>
                        {" · "}
                        Importance: {(f.importance * 100).toFixed(1)}%
                      </div>
                      {f.threshold_context && (
                        <div style={{
                          ...styles.featureCtx,
                          color: THRESHOLD_COLORS[f.threshold_status] || "var(--chalk-dim)",
                        }}>
                          {f.threshold_context}
                        </div>
                      )}
                      <div style={{ ...styles.impBar, width: `${Math.round((f.importance / maxImp) * 100)}%` }} />
                    </div>
                  </div>
                ));
              })()}
              <div style={{ marginTop: 14, fontSize: 11, color: "var(--chalk-dim)" }}>
                Importances from best-selected model (XGBoost, mean decrease in impurity, 5-fold CV).
                Thresholds based on Kuradusenge et al. (2020), Northern Province Rwanda.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
