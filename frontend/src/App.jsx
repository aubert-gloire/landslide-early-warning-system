import { useState } from "react";
import RiskMap from "./components/RiskMap";
import AlertTable from "./components/AlertTable";
import DistrictCards from "./components/DistrictCards";
import PipelineLog from "./components/PipelineLog";
import PredictPanel from "./components/PredictPanel";
import { triggerPipeline } from "./hooks/useApi";

const TABS = ["Risk Map", "Predict", "Alert History", "Districts"];

const styles = {
  root: { minHeight: "100vh", background: "#0f1117", color: "#e2e8f0", display: "flex", flexDirection: "column" },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "14px 24px", background: "#0f1117",
    borderBottom: "1px solid #1e293b", flexWrap: "wrap", gap: 12,
  },
  brand: { display: "flex", flexDirection: "column" },
  title: { fontSize: 16, fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.01em" },
  subtitle: { fontSize: 11, color: "#64748b", marginTop: 2 },
  nav: { display: "flex", gap: 4 },
  tab: (active) => ({
    padding: "6px 16px", borderRadius: 6, fontSize: 13, cursor: "pointer",
    background: active ? "#1e40af" : "transparent",
    color: active ? "#eff6ff" : "#94a3b8",
    border: "none", fontWeight: active ? 600 : 400,
  }),
  actions: { display: "flex", gap: 8 },
  triggerBtn: {
    padding: "6px 14px", background: "#dc2626", color: "#fff",
    border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600,
    cursor: "pointer", letterSpacing: "0.02em",
  },
  content: { flex: 1, padding: 24 },
  mapWrap: { height: "calc(100vh - 140px)", borderRadius: 8, overflow: "hidden" },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 13, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 16 },
  notice: {
    marginBottom: 16, padding: "10px 14px", background: "#1e293b",
    borderLeft: "3px solid #3b82f6", borderRadius: "0 6px 6px 0",
    fontSize: 12, color: "#94a3b8", lineHeight: 1.6,
  },
  toast: (visible) => ({
    position: "fixed", bottom: 24, right: 24, zIndex: 9999,
    background: "#14532d", color: "#86efac", padding: "10px 18px",
    borderRadius: 8, fontSize: 13, fontWeight: 500,
    opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(8px)",
    transition: "all 0.2s ease", pointerEvents: "none",
  }),
};

export default function App() {
  const [activeTab, setActiveTab] = useState("Risk Map");
  const [showLog, setShowLog] = useState(false);
  const [toast, setToast] = useState(null);

  function handleTrigger() {
    setShowLog(true);
  }

  function handlePipelineDone(result) {
    setToast(`Done — ${result.units_processed} units, ${result.alerts_triggered} alerts`);
    setTimeout(() => setToast(null), 5000);
  }

  return (
    <div style={styles.root}>
      <header style={styles.header}>
        <div style={styles.brand}>
          <div style={styles.title}>Landslide Early Warning System</div>
          <div style={styles.subtitle}>Rwanda Northern Province — Gakenke · Burera · Musanze · Gicumbi</div>
        </div>
        <nav style={styles.nav}>
          {TABS.map((t) => (
            <button key={t} style={styles.tab(activeTab === t)} onClick={() => setActiveTab(t)}>{t}</button>
          ))}
        </nav>
        <div style={styles.actions}>
          <button style={styles.triggerBtn} onClick={handleTrigger} disabled={showLog}>
            {showLog ? "Running…" : "Run Pipeline"}
          </button>
        </div>
      </header>

      <main style={styles.content}>
        {(activeTab === "Risk Map" || activeTab === "Predict") && (
          <div style={styles.notice}>
            Decision-support system only. All alerts supplement — and do not replace — official MINEMA and Meteo Rwanda protocols.
          </div>
        )}

        {showLog && (
          <div style={{ marginBottom: 16 }}>
            <PipelineLog
              onDone={handlePipelineDone}
              onClose={() => setShowLog(false)}
            />
          </div>
        )}

        {activeTab === "Risk Map" && (
          <div style={styles.mapWrap}>
            <RiskMap />
          </div>
        )}

        {activeTab === "Predict" && (
          <div>
            <div style={styles.sectionTitle}>Single-Point Prediction &amp; Model Explainability</div>
            <PredictPanel />
          </div>
        )}

        {activeTab === "Alert History" && (
          <div>
            <div style={styles.sectionTitle}>SMS Alert History</div>
            <AlertTable />
          </div>
        )}

        {activeTab === "Districts" && (
          <div>
            <div style={styles.sectionTitle}>District Summary</div>
            <DistrictCards />
          </div>
        )}
      </main>

      <div style={styles.toast(!!toast)}>{toast}</div>
    </div>
  );
}
