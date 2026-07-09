import { useState, useEffect } from "react";
import Dashboard from "./components/Dashboard";
import RiskMap from "./components/RiskMap";
import AlertTable from "./components/AlertTable";
import DistrictCards from "./components/DistrictCards";
import PipelineLog from "./components/PipelineLog";
import PredictPanel from "./components/PredictPanel";
import Login from "./components/Login";
import HelpChat from "./components/HelpChat";

const TABS = ["Overview", "Risk Map", "Predict", "Alerts", "Districts"];

export default function App() {
  const [officer, setOfficer]     = useState(null);
  const [activeTab, setActiveTab] = useState("Overview");
  const [showLog, setShowLog]     = useState(false);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [dashboardKey, setDashboardKey] = useState(0);
  const [toast, setToast]         = useState(null);

  // Restore session on reload
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("officer");
      if (saved) setOfficer(JSON.parse(saved));
    } catch { /* ignore */ }
  }, []);

  function handleLogin(data) { setOfficer(data); }

  function handleLogout() {
    sessionStorage.removeItem("officer");
    setOfficer(null);
  }

  function handlePipelineDone(result) {
    setPipelineRunning(false);
    setDashboardKey(k => k + 1); // force Dashboard to re-fetch fresh data
    setToast(`Run complete — ${result.units_processed} units · ${result.alerts_triggered} alerts`);
    setTimeout(() => setToast(null), 6000);
  }

  function startPipeline() {
    setShowLog(true);
    setPipelineRunning(true);
  }

  if (!officer) return <Login onLogin={handleLogin} />;

  return (
    <div style={{ minHeight: "100vh", background: "var(--ink)", color: "var(--chalk)", display: "flex", flexDirection: "column" }}>

      {/* Top bar */}
      <header style={{
        borderBottom: "1px solid var(--line)",
        padding: "0 28px",
      }}>
        <div style={{
          maxWidth: 1120, margin: "0 auto",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "18px 0", flexWrap: "wrap", gap: 12,
        }}>
          {/* Wordmark */}
          <div style={{
            fontFamily: "'Space Mono', monospace", fontWeight: 700, fontSize: 16,
            letterSpacing: "0.06em", display: "flex", alignItems: "center", gap: 10,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: "50%", background: "var(--ember)",
              boxShadow: "0 0 0 3px rgba(194,75,58,0.25)",
              animation: "pulse 2.4s ease-in-out infinite", display: "inline-block",
            }} />
            Landslide EWS
          </div>

          {/* Nav */}
          <nav style={{ display: "flex", gap: 24, fontSize: 13, letterSpacing: "0.03em" }}>
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setActiveTab(t)}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  color: activeTab === t ? "var(--chalk)" : "var(--chalk-dim)",
                  fontFamily: "inherit", fontSize: 13, padding: "4px 0",
                  borderBottom: activeTab === t ? "1px solid var(--storm)" : "1px solid transparent",
                  transition: "color .15s",
                }}
              >
                {t}
              </button>
            ))}
          </nav>

          {/* Officer + actions */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ fontSize: 12, color: "var(--chalk-dim)", textAlign: "right" }}>
              <span style={{ color: "var(--chalk)", fontWeight: 500 }}>{officer.name}</span>
              {" · "}{officer.district}
            </div>
            <button
              onClick={startPipeline}
              disabled={pipelineRunning}
              style={{
                padding: "7px 14px", borderRadius: "var(--radius)",
                background: "var(--ember)", border: "1px solid var(--ember)",
                color: "#fff", fontSize: 12, fontWeight: 600,
                opacity: pipelineRunning ? 0.6 : 1,
              }}
            >
              {pipelineRunning ? "Running…" : "Run Pipeline"}
            </button>
            <button
              onClick={handleLogout}
              style={{
                padding: "7px 12px", borderRadius: "var(--radius)",
                background: "transparent", border: "1px solid var(--line-strong)",
                color: "var(--chalk-dim)", fontSize: 12,
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main style={{ flex: 1, padding: "28px", maxWidth: 1120, margin: "0 auto", width: "100%" }}>

        {showLog && (
          <div style={{ marginBottom: 24 }}>
            <PipelineLog onDone={handlePipelineDone} onClose={() => setShowLog(false)} />
          </div>
        )}

        {activeTab === "Overview" && (
          <Dashboard key={dashboardKey} onRunPipeline={startPipeline} />
        )}

        {activeTab === "Risk Map" && (
          <>
            <p style={{
              fontFamily: "'Space Mono', monospace", fontSize: 11,
              color: "var(--chalk-dim)", letterSpacing: "0.07em",
              textTransform: "uppercase", marginBottom: 16,
            }}>
              Slope-unit risk map — current assessment
            </p>
            <RiskMap />
            <p style={{
              marginTop: 12, fontSize: 11, color: "var(--chalk-dim)",
              borderLeft: "2px solid var(--line-strong)", paddingLeft: 10,
            }}>
              Decision-support only. All alerts supplement — and do not replace — official MINEMA and Meteo Rwanda protocols.
            </p>
          </>
        )}

        {activeTab === "Predict" && (
          <>
            <p style={{
              fontFamily: "'Space Mono', monospace", fontSize: 11,
              color: "var(--chalk-dim)", letterSpacing: "0.07em",
              textTransform: "uppercase", marginBottom: 20,
            }}>
              Single-point prediction &amp; expert SMS dispatch
            </p>
            <PredictPanel />
          </>
        )}

        {activeTab === "Alerts" && (
          <>
            <p style={{
              fontFamily: "'Space Mono', monospace", fontSize: 11,
              color: "var(--chalk-dim)", letterSpacing: "0.07em",
              textTransform: "uppercase", marginBottom: 20,
            }}>
              SMS dispatch log
            </p>
            <AlertTable />
          </>
        )}

        {activeTab === "Districts" && (
          <>
            <p style={{
              fontFamily: "'Space Mono', monospace", fontSize: 11,
              color: "var(--chalk-dim)", letterSpacing: "0.07em",
              textTransform: "uppercase", marginBottom: 20,
            }}>
              District risk summary
            </p>
            <DistrictCards />
          </>
        )}
      </main>

      {/* Footer */}
      <footer style={{
        borderTop: "1px solid var(--line)", padding: "20px 28px",
        display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12,
        maxWidth: 1120, margin: "0 auto", width: "100%",
      }}>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          background: "rgba(116,147,106,0.12)", color: "var(--moss-text)",
          border: "1px solid rgba(116,147,106,0.3)", borderRadius: 999,
          padding: "5px 14px", fontSize: 11, fontFamily: "'Space Mono', monospace",
        }}>
          ✓ XGBoost · AUC 0.959 · FNR 8.3% · backtested 396 slope units
        </span>
        <span style={{ fontSize: 11, color: "var(--chalk-dim)" }}>
          Data: CHIRPS Preliminary · Copernicus 30m DEM · Sentinel-2 NDVI · ISRIC soil · Africa's Talking
        </span>
      </footer>

      <HelpChat />

      {/* Toast */}
      {toast && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 9999,
          background: "#14532d", color: "#86efac", padding: "10px 18px",
          borderRadius: 8, fontSize: 13, fontWeight: 500,
          border: "1px solid rgba(116,147,106,0.4)",
        }}>
          {toast}
        </div>
      )}
    </div>
  );
}
