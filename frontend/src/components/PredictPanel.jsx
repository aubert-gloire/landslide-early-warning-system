import { useState, useMemo } from "react";
import { useApi } from "../hooks/useApi";
import RadialGauge from "./RadialGauge";
import ThresholdSlider from "./ThresholdSlider";

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

const SLIDER_SPECS = [
  { key: "daily_mm",            label: "Daily Rainfall",       warn: 25,   critical: 50,  unit: "mm" },
  { key: "antecedent_5day_mm",  label: "5-day Antecedent",     warn: 80,   critical: 150, unit: "mm" },
  { key: "twi",                 label: "Topographic Wetness",  warn: 8,    critical: 12,  unit: "" },
  { key: "ndvi",                label: "Vegetation (NDVI)",    warn: 0.35, critical: 0.20, unit: "", invert: true, max: 1 },
];

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
    label: "Edge case — negative rainfall (should be rejected)",
    values: { slope_angle: 30, daily_mm: -20, antecedent_3day_mm: 40, antecedent_5day_mm: 80 },
  },
  {
    label: "Edge case — slope > 90° (should be rejected)",
    values: { slope_angle: 110, daily_mm: 40, antecedent_3day_mm: 55, antecedent_5day_mm: 100 },
  },
];

const styles = {
  root: { display: "grid", gridTemplateColumns: "clamp(280px, 30%, 360px) 1fr", gap: 24, alignItems: "start" },
  panel: { background: "var(--panel)", border: "1px solid var(--line-strong)", borderRadius: 10, padding: 20, boxShadow: "var(--shadow)" },
  sectionTitle: { fontSize: 12, fontWeight: 600, color: "var(--chalk-dim)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12 },
  fieldRow: { marginBottom: 14 },
  label: { display: "block", fontSize: 12, color: "var(--chalk-dim)", marginBottom: 4, fontWeight: 500 },
  input: {
    width: "100%", boxSizing: "border-box",
    background: "var(--panel-2)", border: "1px solid var(--line-strong)", color: "var(--chalk)",
    padding: "7px 10px", borderRadius: 6, fontSize: 13,
  },
  select: {
    width: "100%", boxSizing: "border-box",
    background: "var(--panel-2)", border: "1px solid var(--line-strong)", color: "var(--chalk)",
    padding: "8px 10px", borderRadius: 6, fontSize: 13, marginBottom: 10,
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
  modeTabs: { display: "flex", gap: 6, marginBottom: 20 },
  modeTab: {
    padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600,
    background: "var(--panel-2)", border: "1px solid var(--line-strong)",
    color: "var(--chalk-dim)", cursor: "pointer",
  },
  modeTabActive: { background: "var(--storm)", color: "#fff", borderColor: "var(--storm)" },
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

function ResultPanel({ result, onSendAlert, alertDistrict, setAlertDistrict, alertLoading, alertResult }) {
  const riskColors = RISK_COLORS[result.risk_level] || RISK_COLORS.low;
  const sliderValues = result.features || result.input_summary || {};

  return (
    <div>
      {/* Risk summary */}
      <div style={{ ...styles.panel, borderColor: riskColors.border, marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 16, flexWrap: "wrap" }}>
          <RadialGauge value={result.risk_probability_pct} level={result.risk_level} label="Risk probability" size={88} />
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <RiskBadge level={result.risk_level} />
            {result.alert_triggered && (
              <span style={{ color: "var(--ember)", fontSize: 12, fontWeight: 600 }}>
                Alert threshold exceeded
              </span>
            )}
            {(result.district || result.data_date) && (
              <span style={{ color: "var(--chalk-dim)", fontSize: 12 }}>
                {result.district}{result.sector ? ` · ${result.sector}` : ""}{result.data_date ? ` · data as of ${result.data_date}` : ""}
              </span>
            )}
          </div>
        </div>

        <div style={{ ...styles.sectionTitle, marginTop: 4 }}>Why</div>
        <div style={styles.narrative}>{result.risk_narrative}</div>

        {SLIDER_SPECS.filter((s) => sliderValues[s.key] !== undefined && sliderValues[s.key] !== null).map((s) => (
          <ThresholdSlider
            key={s.key}
            label={s.label}
            value={sliderValues[s.key]}
            warn={s.warn}
            critical={s.critical}
            unit={s.unit}
            max={s.max}
            invert={s.invert}
          />
        ))}
      </div>

      {/* SMS dispatch */}
      <div style={{ ...styles.panel, marginBottom: 16, borderColor: result.alert_triggered ? "var(--ember)" : "var(--line-strong)" }}>
        <div style={styles.sectionTitle}>Send SMS Alert</div>
        <p style={{ fontSize: 12, color: "var(--chalk-dim)", marginBottom: 12, marginTop: 0 }}>
          Sends to all registered officers in the district.
          {!result.alert_triggered && " Below alert threshold — use Force Send to override."}
        </p>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
          <input
            type="text"
            placeholder="District (e.g. Musanze)"
            value={alertDistrict}
            onChange={(e) => setAlertDistrict(e.target.value)}
            style={{ ...styles.input, flex: 1, minWidth: 160 }}
          />
          <button
            onClick={() => onSendAlert(false)}
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
            onClick={() => onSendAlert(true)}
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
              Sent to {alertResult.sms_count} recipient{alertResult.sms_count !== 1 ? "s" : ""} in {alertResult.district}
              {alertResult.forced && <span style={{ color: "var(--amber-text)" }}> (manual override)</span>}
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
        <div style={styles.sectionTitle}>What's driving this</div>
        {(() => {
          const maxImp = Math.max(...result.top_features.map((f) => f.importance), 0.001);
          return result.top_features.map((f, i) => (
            <div key={f.feature} style={styles.featureRow}>
              <div style={styles.rank}>{i + 1}</div>
              <div style={{ flex: 1 }}>
                <div style={styles.featureName}>{f.label}</div>
                <div style={styles.featureValue}>
                  Value: <strong>{f.value ?? "N/A"}</strong>
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
      </div>
    </div>
  );
}

function OfficerMode() {
  const { data: mapData, loading: mapLoading } = useApi("/api/risk-map");
  const [district, setDistrict] = useState("");
  const [unitId, setUnitId] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [alertDistrict, setAlertDistrict] = useState("");
  const [alertLoading, setAlertLoading] = useState(false);
  const [alertResult, setAlertResult] = useState(null);

  const units = mapData?.features || [];
  const districts = useMemo(
    () => [...new Set(units.map((f) => f.properties.district))].filter(Boolean).sort(),
    [units]
  );
  const unitsInDistrict = useMemo(
    () => units
      .filter((f) => !district || f.properties.district === district)
      .sort((a, b) => b.properties.risk_probability - a.properties.risk_probability),
    [units, district]
  );

  async function selectUnit(id) {
    setUnitId(id);
    setResult(null);
    setError(null);
    setAlertResult(null);
    if (!id) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/predict/unit/${id}`);
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || `Error ${res.status}`);
        return;
      }
      setResult(data);
      setAlertDistrict(data.district || "");
    } catch (err) {
      setError(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleSendAlert(force = false) {
    if (!result) return;
    setAlertLoading(true);
    setAlertResult(null);
    const body = { district: alertDistrict, force, ...result.features };
    try {
      const res = await fetch(`${API_BASE}/api/predict/alert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setAlertResult(res.ok ? data : { error: data.detail || `Error ${res.status}` });
    } catch (err) {
      setAlertResult({ error: `Network error: ${err.message}` });
    } finally {
      setAlertLoading(false);
    }
  }

  return (
    <div style={styles.root}>
      <div>
        <div style={styles.panel}>
          <div style={styles.sectionTitle}>Select Location</div>
          <label style={styles.label}>District</label>
          <select style={styles.select} value={district} onChange={(e) => { setDistrict(e.target.value); selectUnit(""); }}>
            <option value="">All districts</option>
            {districts.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>

          <label style={styles.label}>Slope unit</label>
          <select
            style={styles.select}
            value={unitId}
            onChange={(e) => selectUnit(e.target.value)}
            disabled={mapLoading || !unitsInDistrict.length}
          >
            <option value="">
              {mapLoading ? "Loading…" : unitsInDistrict.length ? "Choose a unit" : "No assessment run yet"}
            </option>
            {unitsInDistrict.map((f) => (
              <option key={f.properties.unit_id} value={f.properties.unit_id}>
                Unit {f.properties.unit_id} — {f.properties.sector || f.properties.district} ({Math.round(f.properties.risk_probability * 100)}%)
              </option>
            ))}
          </select>
          <div style={styles.hint}>
            Values shown are pulled directly from the most recent pipeline run — nothing to type in.
          </div>
        </div>
      </div>

      <div>
        {!result && !error && !loading && (
          <div style={{ ...styles.panel, color: "var(--chalk-dim)", fontSize: 13, lineHeight: 1.8 }}>
            Pick a district and slope unit to see its current risk assessment.
          </div>
        )}
        {loading && (
          <div style={{ ...styles.panel, color: "var(--chalk-dim)", fontSize: 13 }}>Loading assessment…</div>
        )}
        {error && (
          <div style={styles.errorBox}>
            <div style={styles.errorTitle}>Couldn't load this unit</div>
            <div style={{ color: "var(--ember-text)", fontSize: 13 }}>{error}</div>
          </div>
        )}
        {result && (
          <ResultPanel
            result={result}
            onSendAlert={handleSendAlert}
            alertDistrict={alertDistrict}
            setAlertDistrict={setAlertDistrict}
            alertLoading={alertLoading}
            alertResult={alertResult}
          />
        )}
      </div>
    </div>
  );
}

function AdvancedMode() {
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
    for (const [k, v] of Object.entries(preset.values)) next[k] = String(v);
    setForm(next);
    setResult(null);
    setValidationErrors(null);
    setFieldErrors({});
  }

  function parsedFeatures() {
    const body = {};
    for (const [k, meta] of Object.entries(FIELD_META)) {
      const raw = form[k].trim();
      if (raw === "") continue;
      body[k] = k === "soil_class" ? parseInt(raw, 10) : parseFloat(raw);
    }
    return body;
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
        if (meta.required) setFieldErrors((err) => ({ ...err, [k]: "Required" }));
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
      setResult(await res.json());
    } catch (err) {
      setValidationErrors([{ field: "network", message: `Network error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSendAlert(force = false) {
    setAlertLoading(true);
    setAlertResult(null);
    const body = { district: alertDistrict, force, ...parsedFeatures() };
    try {
      const res = await fetch(`${API_BASE}/api/predict/alert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setAlertResult(res.ok ? data : { error: data.detail || `Error ${res.status}` });
    } catch (err) {
      setAlertResult({ error: `Network error: ${err.message}` });
    } finally {
      setAlertLoading(false);
    }
  }

  return (
    <div style={styles.root}>
      <div>
        <div style={styles.panel}>
          <div style={styles.sectionTitle}>Scenario Presets</div>
          {SCENARIO_PRESETS.map((p) => {
            const isEdgeCase = p.label.startsWith("Edge case");
            return (
              <button
                key={p.label}
                style={{ ...styles.presetBtn, ...(isEdgeCase ? styles.invalidPreset : {}) }}
                onClick={() => applyPreset(p)}
              >
                {p.label}
              </button>
            );
          })}
        </div>

        <div style={{ ...styles.panel, marginTop: 16 }}>
          <div style={styles.sectionTitle}>Manual Feature Entry</div>
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
                  style={{ ...styles.input, ...(fieldErrors[field] ? styles.errorInput : {}) }}
                />
                {fieldErrors[field] && (
                  <div style={{ color: "var(--ember-text)", fontSize: 11, marginTop: 3 }}>{fieldErrors[field]}</div>
                )}
                <div style={styles.hint}>{meta.hint}</div>
              </div>
            ))}
            <button type="submit" style={styles.btn} disabled={loading}>
              {loading ? "Running…" : "Run Prediction"}
            </button>
          </form>
        </div>
      </div>

      <div>
        {!result && !validationErrors && (
          <div style={{ ...styles.panel, color: "var(--chalk-dim)", fontSize: 13, lineHeight: 1.8 }}>
            <strong style={{ color: "var(--chalk)" }}>Scenario testing</strong>
            <p style={{ marginTop: 8 }}>
              Enter feature values by hand or pick a preset, then run the prediction. Use this to test
              hypothetical conditions — for real slope units, use the main Predict view instead.
            </p>
          </div>
        )}

        {validationErrors && (
          <div style={styles.errorBox}>
            <div style={styles.errorTitle}>Input rejected</div>
            <p style={{ color: "var(--chalk-dim)", fontSize: 12, marginBottom: 12 }}>
              Fix the values below and try again:
            </p>
            {validationErrors.map((err, i) => (
              <div key={i} style={styles.errorItem}>
                <strong>{err.field}:</strong> {err.message}
                {err.value !== undefined && (
                  <span style={{ color: "var(--chalk-dim)" }}> (got: {JSON.stringify(err.value)})</span>
                )}
              </div>
            ))}
          </div>
        )}

        {result && (
          <ResultPanel
            result={result}
            onSendAlert={handleSendAlert}
            alertDistrict={alertDistrict}
            setAlertDistrict={setAlertDistrict}
            alertLoading={alertLoading}
            alertResult={alertResult}
          />
        )}
      </div>
    </div>
  );
}

export default function PredictPanel() {
  const [mode, setMode] = useState("officer");

  return (
    <div>
      <div style={styles.modeTabs}>
        <button
          style={{ ...styles.modeTab, ...(mode === "officer" ? styles.modeTabActive : {}) }}
          onClick={() => setMode("officer")}
        >
          By Slope Unit
        </button>
        <button
          style={{ ...styles.modeTab, ...(mode === "advanced" ? styles.modeTabActive : {}) }}
          onClick={() => setMode("advanced")}
        >
          Advanced / Scenario Testing
        </button>
      </div>
      {mode === "officer" ? <OfficerMode /> : <AdvancedMode />}
    </div>
  );
}
