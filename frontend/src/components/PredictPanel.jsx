import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

const RISK_COLORS = {
  critical: { bg: "#450a0a", text: "#fca5a5", border: "#dc2626" },
  high:     { bg: "#431407", text: "#fdba74", border: "#ea580c" },
  medium:   { bg: "#422006", text: "#fcd34d", border: "#ca8a04" },
  low:      { bg: "#052e16", text: "#86efac", border: "#16a34a" },
};
const THRESHOLD_COLORS = {
  critical: "#fca5a5",
  elevated: "#fcd34d",
  normal:   "#86efac",
  no_threshold: "#94a3b8",
  no_value: "#64748b",
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
  panel: { background: "#111827", border: "1px solid #1e293b", borderRadius: 8, padding: 20 },
  sectionTitle: { fontSize: 12, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12 },
  fieldRow: { marginBottom: 14 },
  label: { display: "block", fontSize: 12, color: "#94a3b8", marginBottom: 4, fontWeight: 500 },
  input: {
    width: "100%", boxSizing: "border-box",
    background: "#1e293b", border: "1px solid #334155", color: "#e2e8f0",
    padding: "7px 10px", borderRadius: 6, fontSize: 13,
  },
  hint: { fontSize: 11, color: "#475569", marginTop: 3 },
  errorInput: { borderColor: "#dc2626" },
  btn: {
    width: "100%", padding: "10px 0", background: "#1d4ed8",
    color: "#fff", border: "none", borderRadius: 6, fontSize: 14,
    fontWeight: 600, cursor: "pointer", marginTop: 8,
  },
  presetBtn: {
    display: "block", width: "100%", textAlign: "left",
    padding: "7px 10px", background: "#1e293b", border: "1px solid #334155",
    color: "#94a3b8", borderRadius: 6, fontSize: 12, cursor: "pointer",
    marginBottom: 6,
  },
  invalidPreset: { borderColor: "#dc2626", color: "#fca5a5" },
  divider: { borderColor: "#1e293b", margin: "16px 0" },
  narrative: { lineHeight: 1.7, fontSize: 14, color: "#e2e8f0", marginBottom: 16 },
  featureRow: {
    display: "flex", alignItems: "flex-start", gap: 10,
    padding: "10px 0", borderBottom: "1px solid #1e293b",
  },
  rank: { fontSize: 18, fontWeight: 700, color: "#334155", minWidth: 24, textAlign: "center" },
  featureName: { fontWeight: 600, fontSize: 13, color: "#e2e8f0" },
  featureValue: { fontSize: 12, color: "#94a3b8" },
  featureCtx: { fontSize: 12, marginTop: 2 },
  impBar: { height: 4, borderRadius: 2, background: "#1d4ed8", marginTop: 6 },
  errorBox: { background: "#450a0a", border: "1px solid #dc2626", borderRadius: 8, padding: 16 },
  errorTitle: { color: "#fca5a5", fontWeight: 600, fontSize: 13, marginBottom: 8 },
  errorItem: { color: "#fca5a5", fontSize: 13, marginBottom: 4 },
  metricRow: { display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" },
  metric: { flex: 1, minWidth: 120, background: "#1e293b", borderRadius: 8, padding: "12px 16px" },
  metricVal: { fontSize: 24, fontWeight: 700 },
  metricLabel: { fontSize: 11, color: "#64748b", marginTop: 2 },
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
        // Pydantic validation failed — show field-level errors
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
                  {meta.required && <span style={{ color: "#dc2626" }}> *</span>}
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
                  <div style={{ color: "#f87171", fontSize: 11, marginTop: 3 }}>{fieldErrors[field]}</div>
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
          <div style={{ ...styles.panel, color: "#475569", fontSize: 13, lineHeight: 1.8 }}>
            <strong style={{ color: "#94a3b8" }}>How to use this panel</strong>
            <p style={{ marginTop: 8 }}>
              Select a preset scenario or enter feature values manually, then click <em>Run Prediction</em>.
            </p>
            <p>
              The model returns a risk probability, risk level, and a narrative explaining which features
              are driving the classification — with reference to the evidence-based thresholds from
              Kuradusenge et al. (2020).
            </p>
            <p>
              Try the two <span style={{ color: "#fca5a5" }}>invalid presets</span> to see how the API
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
            <p style={{ color: "#94a3b8", fontSize: 12, marginBottom: 12 }}>
              The API rejected the request before running the model. Fix the inputs below:
            </p>
            {validationErrors.map((err, i) => (
              <div key={i} style={styles.errorItem}>
                <strong>{err.field}:</strong> {err.message}
                {err.value !== undefined && (
                  <span style={{ color: "#94a3b8" }}> (got: {JSON.stringify(err.value)})</span>
                )}
              </div>
            ))}
            <p style={{ color: "#64748b", fontSize: 11, marginTop: 12, marginBottom: 0 }}>
              This demonstrates system robustness — invalid data is rejected at the API boundary,
              never reaching the model or database.
            </p>
          </div>
        )}

        {result && (
          <div>
            {/* Risk summary */}
            <div style={{
              ...styles.panel,
              borderColor: riskColors.border,
              marginBottom: 16,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <RiskBadge level={result.risk_level} />
                <span style={{ color: "#64748b", fontSize: 12 }}>
                  Alert threshold: {Math.round(result.production_threshold * 100)}%
                </span>
                {result.alert_triggered && (
                  <span style={{ color: "#dc2626", fontSize: 12, fontWeight: 600 }}>
                    ⚠ SMS ALERT WOULD BE SENT
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
                  <div style={{ ...styles.metricVal, color: result.alert_triggered ? "#dc2626" : "#86efac" }}>
                    {result.alert_triggered ? "YES" : "NO"}
                  </div>
                  <div style={styles.metricLabel}>Alert Triggered</div>
                </div>
                <div style={styles.metric}>
                  <div style={{ ...styles.metricVal, color: "#94a3b8", fontSize: 16 }}>
                    {result.input_summary.slope_angle}° / {result.input_summary.daily_mm}mm
                  </div>
                  <div style={styles.metricLabel}>Slope / Daily Rain</div>
                </div>
              </div>

              {/* Risk narrative */}
              <div style={{ ...styles.sectionTitle, marginTop: 4 }}>Model Reasoning</div>
              <div style={styles.narrative}>{result.risk_narrative}</div>
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
                          color: THRESHOLD_COLORS[f.threshold_status] || "#94a3b8",
                        }}>
                          {f.threshold_context}
                        </div>
                      )}
                      <div style={{ ...styles.impBar, width: `${Math.round((f.importance / maxImp) * 100)}%` }} />
                    </div>
                  </div>
                ));
              })()}
              <div style={{ marginTop: 14, fontSize: 11, color: "#475569" }}>
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
