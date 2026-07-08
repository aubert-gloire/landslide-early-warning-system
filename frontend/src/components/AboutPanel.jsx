const styles = {
  root: { maxWidth: 860, margin: "0 auto", lineHeight: 1.7 },
  h2: { fontSize: 20, fontWeight: 700, color: "#e2e8f0", marginBottom: 6 },
  h3: { fontSize: 14, fontWeight: 700, color: "#93c5fd", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8, marginTop: 24 },
  p: { color: "#94a3b8", fontSize: 14, marginBottom: 12 },
  sub: { color: "#64748b", fontSize: 13, marginBottom: 20 },
  divider: { borderColor: "#1e293b", margin: "20px 0" },
  flow: { display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 20 },
  step: { background: "#1e293b", border: "1px solid #334155", borderRadius: 8, padding: "10px 16px", fontSize: 13, color: "#cbd5e1", flex: "1 1 150px" },
  stepNum: { fontSize: 11, color: "#3b82f6", fontWeight: 700, marginBottom: 4 },
  obj: { background: "#0f172a", border: "1px solid #1e3a5f", borderRadius: 8, padding: "12px 16px", marginBottom: 10 },
  objTitle: { fontSize: 12, fontWeight: 700, color: "#60a5fa", marginBottom: 4 },
  objText: { fontSize: 13, color: "#94a3b8" },
  metricGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 20 },
  metric: { background: "#1e293b", border: "1px solid #334155", borderRadius: 8, padding: "12px 14px" },
  metricVal: { fontSize: 22, fontWeight: 700, color: "#86efac" },
  metricLabel: { fontSize: 11, color: "#64748b", marginTop: 2 },
  tag: { display: "inline-block", padding: "2px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600, background: "#1e3a5f", color: "#93c5fd", marginRight: 6, marginBottom: 6 },
};

const OBJECTIVES = [
  {
    num: "Obj 1",
    title: "Data Integration",
    text: "Collect and integrate CHIRPS rainfall, Copernicus DEM, Sentinel-2 NDVI, ISRIC soil, and NASA COOLR datasets into a slope-unit feature matrix for Rwanda's Northern Province, with 5-day antecedent rainfall as primary predictor.",
    status: "✅ Met",
  },
  {
    num: "Obj 2",
    title: "ML Model & Automated Pipeline",
    text: "Train and optimise a classifier achieving FNR < 5% via threshold tuning and ablation studies. Deploy automated daily pipeline ingesting CHIRPS, running inference, storing results in MongoDB Atlas, and dispatching GPS-precise SMS alerts via Africa's Talking.",
    status: "⚠️ Partially met — FNR 8.33% (mathematical floor: 1 missed event out of 12 positive labels). XGBoost selected over RF after comparison (AUC 0.959 vs 0.619). GPS coordinates added to SMS.",
  },
  {
    num: "Obj 3",
    title: "Evaluation & Live System",
    text: "Backtest against May 2023 Northern Province landslide event. Measure AUC, FNR, FPR against Kuradusenge et al. (2020) benchmarks. Demonstrate fully operational live system.",
    status: "✅ Met — 3/4 historical events detected. AUC 0.959 exceeds benchmark. Live at landslide-early-warning-system-zeta.vercel.app",
  },
];

export default function AboutPanel() {
  return (
    <div style={styles.root}>
      <div style={styles.h2}>ML-Based Landslide Early Warning System</div>
      <div style={styles.sub}>
        BSc Software Engineering Capstone · African Leadership University · Supervised by Dirac Murairi
      </div>

      <div style={{ marginBottom: 16 }}>
        {["Climate Adaptation", "Disaster Risk Reduction", "Rwanda Northern Province", "MINEMA Protocols", "Sustainable Development"].map(t => (
          <span key={t} style={styles.tag}>{t}</span>
        ))}
      </div>

      <hr style={styles.divider} />

      <div style={styles.h3}>Problem Statement</div>
      <p style={styles.p}>
        Rwanda's Northern Province — covering Gakenke, Burera, Musanze, and Gicumbi districts — is one of the most
        landslide-prone regions in sub-Saharan Africa. Steep volcanic terrain combined with intense seasonal rainfall
        creates repeated mass-movement events that kill residents and destroy infrastructure. Existing warning systems
        rely on manual observation with no quantified risk scores, no automated alerts, and no geographic specificity
        below the district level.
      </p>
      <p style={styles.p}>
        This system addresses that gap by providing <strong style={{ color: "#e2e8f0" }}>daily automated risk predictions
        at slope-unit level (~5.5 km²)</strong>, dispatching GPS-precise SMS alerts to district officers, and presenting
        a live risk dashboard — enabling proactive evacuation decisions rather than reactive response.
      </p>

      <hr style={styles.divider} />

      <div style={styles.h3}>How It Works</div>
      <div style={styles.flow}>
        {[
          { n: "01", label: "CHIRPS rainfall downloaded daily at 06:00 Kigali time" },
          { n: "02", label: "Feature matrix built: terrain + NDVI + soil + antecedent rainfall" },
          { n: "03", label: "XGBoost model scores each of 396 slope units" },
          { n: "04", label: "Risk map stored in MongoDB Atlas as GeoJSON" },
          { n: "05", label: "High-risk units trigger GPS-precise SMS via Africa's Talking" },
          { n: "06", label: "Officers confirm/deny via SMS reply — feedback updates dashboard" },
        ].map(s => (
          <div key={s.n} style={styles.step}>
            <div style={styles.stepNum}>STEP {s.n}</div>
            {s.label}
          </div>
        ))}
      </div>

      <hr style={styles.divider} />

      <div style={styles.h3}>Model Performance</div>
      <div style={styles.metricGrid}>
        {[
          { val: "0.959", label: "Cross-val AUC" },
          { val: "8.33%", label: "False Negative Rate" },
          { val: "3.0%", label: "False Positive Rate" },
          { val: "3 / 4", label: "Historical events detected" },
          { val: "0.05", label: "Production threshold" },
          { val: "396", label: "Slope units monitored" },
        ].map(m => (
          <div key={m.label} style={styles.metric}>
            <div style={styles.metricVal}>{m.val}</div>
            <div style={styles.metricLabel}>{m.label}</div>
          </div>
        ))}
      </div>

      <hr style={styles.divider} />

      <div style={styles.h3}>Capstone Objectives</div>
      {OBJECTIVES.map(o => (
        <div key={o.num} style={styles.obj}>
          <div style={styles.objTitle}>{o.num} — {o.title}</div>
          <div style={styles.objText}>{o.text}</div>
          <div style={{ marginTop: 6, fontSize: 12, color: o.status.startsWith("✅") ? "#86efac" : "#fcd34d" }}>{o.status}</div>
        </div>
      ))}

      <hr style={styles.divider} />

      <div style={styles.h3}>Key References</div>
      <p style={styles.p}>
        Kuradusenge et al. (2020) — Rainfall-induced landslide susceptibility mapping using machine learning in Rwanda Northern Province. Benchmarks used: AUC, FNR, FPR on Rwandan terrain data.
      </p>
    </div>
  );
}
