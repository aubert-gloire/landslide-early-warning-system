import { useState, useEffect, useRef } from "react";

const BOT_NAME = "EWS Guide";

const WELCOME = `Hello! I'm the Landslide EWS assistant. I can help you understand how to use this system.\n\nTry one of the quick questions below, or type your own.`;

const QA = [
  {
    triggers: ["risk map", "map", "colour", "color", "circle", "dot", "what do the"],
    answer: `The Risk Map shows all 396 slope units in Rwanda's Northern Province as coloured circles:\n\n🟢 Green — low risk (below 50%)\n🟡 Amber — moderate risk (50–79%)\n🔴 Red — high risk (≥80%) — an SMS alert is sent\n\nClick any circle to see the unit ID, district, risk %, and whether an alert was dispatched.\n\nThe map legend shows two dates:\n• Assessment date — when the pipeline last ran\n• Rainfall data to — the most recent date for which CHIRPS rainfall data was available (typically 4 days behind today due to the CHIRPS Preliminary processing lag)\n\nThis means the map shows today's best possible risk assessment, not a real-time reading. This is standard for operational early warning systems — the data lag is transparent in the legend.`,
  },
  {
    triggers: ["predict", "prediction", "run prediction", "feature", "input", "slope", "rainfall", "how to use predict"],
    answer: `The Predict panel lets you test the XGBoost model against any input:\n\n1. Choose a scenario preset (high / medium / low risk), or fill in values manually.\n2. Required fields: Slope Angle, Daily Rainfall, 3-day and 5-day antecedent rainfall.\n3. Click "Run Prediction" — the model returns a risk %, risk level, and explanation of which features drove the result.\n4. Try the "Invalid" presets to see how the API rejects impossible values (e.g. negative rainfall) with a 422 error before the model even runs.`,
  },
  {
    triggers: ["alert", "sms", "send alert", "dispatch", "officer", "expert"],
    answer: `SMS alerts are sent automatically during the pipeline run to registered field officers whenever a slope unit exceeds the 5% production risk threshold.\n\nYou can also send a manual alert from the Predict panel:\n• Fill in feature values and run a prediction.\n• In the "Expert SMS Dispatch" section, enter a district name and click "Send SMS Alert".\n• If the risk is below threshold, use "Force Send" to override — this is intended for meteorologists who have additional context.\n\nAll sent alerts appear in the Alerts tab with delivery status and officer feedback.`,
  },
  {
    triggers: ["pipeline", "run pipeline", "what is pipeline", "trigger", "cron", "schedule", "daily"],
    answer: `The pipeline is the core automated process. Click "Run Pipeline" in the top-right corner to start it.\n\nIt does the following in order:\n1. Downloads latest CHIRPS Preliminary rainfall data (4-day lag).\n2. Merges rainfall with terrain features (slope, TWI, NDVI, soil) for all 396 slope units.\n3. Runs the XGBoost model to score every unit.\n4. Sends SMS alerts for any unit above the risk threshold.\n5. Saves results to MongoDB.\n\nThe pipeline also runs automatically every day at 10:00 AM Kigali time via GitHub Actions.`,
  },
  {
    triggers: ["district", "districts", "gakenke", "burera", "musanze", "gicumbi", "district card"],
    answer: `The Districts tab shows a summary card for each of the 4 monitored districts in Northern Province:\n\n• Peak risk today — highest risk probability among all slope units in that district.\n• Slope units monitored — how many slope units are tracked.\n• Alerts (last 7 days) — count of SMS alerts dispatched recently.\n\nDistricts are colour-coded by accent (blue, green, amber, red) for quick identification.`,
  },
  {
    triggers: ["chirps", "rainfall data", "data source", "satellite", "where does", "where does the data"],
    answer: `Rainfall data comes from CHIRPS v2 Preliminary — a satellite-derived rainfall product from the Climate Hazards Group at UC Santa Barbara.\n\nWhy Preliminary? The Final CHIRPS product has a ~3-week lag, which is too slow for early warning. The Preliminary product has only a ~4-day lag and the same spatial resolution (0.05°), making it suitable for near-real-time use.\n\nOther data sources:\n• Terrain (slope, TWI) — Copernicus 30m DEM\n• Vegetation — Sentinel-2 NDVI via Google Earth Engine\n• Soil — ISRIC SoilGrids\n• SMS delivery — Africa's Talking API`,
  },
  {
    triggers: ["model", "xgboost", "machine learning", "ai", "accuracy", "auc", "how accurate", "train"],
    answer: `The system uses an XGBoost classifier trained on historical rainfall and terrain data for Northern Province Rwanda, following the thresholds from Kuradusenge et al. (2020).\n\nModel performance (5-fold cross-validation, 396 slope units):\n• AUC: 0.959\n• False Negative Rate: 8.3%\n• Production threshold: 5% (set low to minimise missed alerts)\n\nClass imbalance was handled with SMOTE oversampling inside an ImbPipeline to prevent data leakage.`,
  },
  {
    triggers: ["login", "password", "sign in", "credentials", "account", "username", "who can"],
    answer: `The login page has two options:\n\n1. District Officer — click your district button (Gakenke, Burera, Musanze, Gicumbi) or System Admin to sign in. No password required — the button identifies you.\n\n2. Guest — click "Continue as Guest" to access the full system without identifying as a specific officer.\n\nAll accounts (officers and guest) have identical access to every tab and feature. The district name shown in the header is for identification only — it does not restrict what you can see or do.`,
  },
  {
    triggers: ["threshold", "probability", "5%", "percent", "what does", "what is the threshold"],
    answer: `The production risk threshold is set at 5% probability.\n\nThis means: if the model predicts a ≥5% chance of landslide for a slope unit, an SMS alert is sent. The threshold is intentionally low to minimise false negatives (missed real events), at the cost of more false positives.\n\nThe risk bands displayed on the map use higher thresholds for visual clarity:\n• Low: below 50%\n• Moderate: 50–79%\n• High: 80%+\n\nBut alerts are always sent at 5%+.`,
  },
  {
    triggers: ["feedback", "confirm", "denied", "reply", "officer feedback", "sms reply"],
    answer: `After an SMS alert is sent, field officers can reply by SMS:\n• Reply "Y" to confirm the alert (ground-truthed event)\n• Reply "N" to deny it (false alarm)\n\nFeedback is shown in the Alerts tab under "Officer Feedback" and tracked in the stats panel at the top (Confirmed / Denied / Awaiting). The confirmation rate gives a real-world accuracy measure over time.`,
  },
  {
    triggers: ["slope unit", "what is a slope unit", "unit", "396", "terrain unit", "hydrological"],
    answer: `A slope unit is a hydrological terrain subdivision — an area of land defined by ridge lines and valley lines where water drains in a consistent direction.\n\nThis system monitors 396 slope units across Northern Province Rwanda. Each unit is a polygon derived from the Copernicus 30m DEM using watershed analysis.\n\nWhy slope units instead of pixels? They are more physically meaningful for landslide modelling — a single slope unit represents one coherent hillside that behaves uniformly under rainfall. This is the standard approach in the scientific literature (Kuradusenge et al., 2020).`,
  },
  {
    triggers: ["antecedent", "3-day", "5-day", "10-day", "prior rainfall", "what is antecedent", "cumulative"],
    answer: `Antecedent rainfall is the cumulative rainfall that fell in the days before today — it measures how saturated the soil already is.\n\n• 3-day antecedent — last 3 days total (mm). High values mean shallow soil layers are saturated.\n• 5-day antecedent — last 5 days total (mm). Critical threshold: above 150mm significantly raises risk.\n• 10-day antecedent — last 10 days total (mm). Indicates deeper clay layer saturation.\n\nResearch shows antecedent rainfall is often more important than daily rainfall alone — a moderate storm on already-saturated ground is far more dangerous than heavy rain on dry soil.`,
  },
  {
    triggers: ["twi", "topographic wetness", "ndvi", "vegetation index", "what is twi", "what is ndvi"],
    answer: `TWI — Topographic Wetness Index — measures how likely water is to accumulate at a point based on slope and upstream drainage area. Higher TWI means water pools there more easily.\n• Critical threshold: TWI above 12 significantly raises landslide risk.\n• Derived from the Copernicus 30m DEM.\n\nNDVI — Normalised Difference Vegetation Index — measures vegetation density from Sentinel-2 satellite imagery.\n• Range: -1 to 1. Values below 0.35 indicate sparse or absent vegetation.\n• Why it matters: vegetation roots stabilise slopes. Deforested or degraded hillsides (low NDVI) are significantly more susceptible to failure.`,
  },
  {
    triggers: ["log", "pipeline log", "cache hit", "mongodb", "0 units", "zero alerts", "no alert", "what does it mean", "stream"],
    answer: `The pipeline log streams each step in real time as the run progresses. Here is what the key messages mean:\n\n• "MongoDB cache hit" — recent rainfall data was found in the database, so no CHIRPS download was needed. This is the fast path.\n• "Scoring all slope units with XGBoost" — the model is running across all 396 units.\n• "0 units above threshold" — the system ran successfully and found no high-risk units today. This is normal during dry periods. It is not an error.\n• "✓ Pipeline complete" — all steps finished. The risk map and district cards are now updated.\n\nIf you see a red "Error" status, it usually means a network issue with the CHIRPS download or the API server.`,
  },
  {
    triggers: ["alerts tab", "alert table", "alert history", "view alerts", "past alerts", "how to see alerts", "filter"],
    answer: `The Alerts tab shows a log of every SMS alert dispatched by the system.\n\nHow to use it:\n• Use the district dropdown to filter alerts by district (Gakenke, Burera, Musanze, Gicumbi).\n• Click "Refresh" to reload the latest data.\n• The stats panel at the top shows totals: alerts sent, confirmed, denied, awaiting feedback, and confirmation rate.\n\nColumn meanings:\n• Sent at — date and time the SMS was dispatched\n• Unit ID — the slope unit that triggered the alert\n• Risk % — model probability at the time\n• Status — SMS delivery status (sent / delivered / failed)\n• Officer Feedback — Y/N reply from the field officer`,
  },
  {
    triggers: ["why northern province", "why 4 districts", "why not all rwanda", "coverage", "which area", "geographic", "scope"],
    answer: `The system currently covers Northern Province Rwanda — specifically the districts of Gakenke, Burera, Musanze, and Gicumbi.\n\nThis focus was chosen because:\n• Northern Province has the highest historical landslide incidence in Rwanda, driven by steep volcanic terrain and high seasonal rainfall.\n• The training dataset (Kuradusenge et al., 2020) was built specifically for this region, so the model's learned thresholds are calibrated for Northern Province soil, slope, and rainfall patterns.\n• MINEMA (National Disaster Management Authority) has identified this province as a priority zone for early warning.\n\nExtending coverage to other provinces would require retraining with region-specific data.`,
  },
  {
    triggers: ["session", "sign out", "logout", "how long", "expires", "switch account", "signed out", "session expired"],
    answer: `Each login session lasts 24 hours. After 24 hours your session expires automatically and you will be asked to sign in again.\n\nTo sign out manually: click the "Sign out" button in the top-right corner of the header. This clears your session from the browser immediately.\n\nTo switch accounts: sign out first, then sign in with the other username. All accounts share the same password.\n\nNote: sessions are stored in your browser's sessionStorage, so closing the browser tab will also end your session.`,
  },
];

const FALLBACK = `I'm not sure about that specific question. Try asking about:\n\n• What a slope unit is\n• The risk map and colour coding\n• What antecedent rainfall means\n• How to run a prediction\n• How SMS alerts work\n• What the pipeline log messages mean\n• The XGBoost model and accuracy\n• Why the system covers Northern Province\n• Data sources (CHIRPS, DEM, NDVI, TWI)`;

const QUICK_REPLIES = [
  "What is a slope unit?",
  "How does the risk map work?",
  "How do I run a prediction?",
  "When are SMS alerts sent?",
  "What does the pipeline do?",
  "Why only Northern Province?",
  "How accurate is the model?",
];

function matchAnswer(text) {
  const lower = text.toLowerCase();
  for (const { triggers, answer } of QA) {
    if (triggers.some((t) => lower.includes(t))) return answer;
  }
  return FALLBACK;
}

function Message({ msg }) {
  const isBot = msg.role === "bot";
  return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: isBot ? "flex-start" : "flex-end",
      marginBottom: 12,
    }}>
      {isBot && (
        <span style={{ fontSize: 10, color: "var(--chalk-dim)", marginBottom: 3, fontFamily: "'Space Mono', monospace" }}>
          {BOT_NAME}
        </span>
      )}
      <div style={{
        maxWidth: "85%", padding: "10px 13px", borderRadius: isBot ? "4px 14px 14px 14px" : "14px 4px 14px 14px",
        background: isBot ? "var(--panel-2)" : "var(--ember)",
        color: isBot ? "var(--chalk)" : "#fff",
        fontSize: 13, lineHeight: 1.6,
        border: isBot ? "1px solid var(--line)" : "none",
        whiteSpace: "pre-wrap",
      }}>
        {msg.text}
      </div>
    </div>
  );
}

export default function HelpChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [hasOpened, setHasOpened] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open && !hasOpened) {
      setMessages([{ role: "bot", text: WELCOME }]);
      setHasOpened(true);
    }
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function send(text) {
    const trimmed = text.trim();
    if (!trimmed) return;
    const userMsg = { role: "user", text: trimmed };
    const botMsg  = { role: "bot",  text: matchAnswer(trimmed) };
    setMessages((prev) => [...prev, userMsg, botMsg]);
    setInput("");
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  return (
    <>
      {/* Chat panel */}
      {open && (
        <div style={{
          position: "fixed", bottom: 84, right: 24, zIndex: 9990,
          width: 340, maxHeight: 520,
          background: "var(--panel)", border: "1px solid var(--line-strong)",
          borderRadius: 14, display: "flex", flexDirection: "column",
          boxShadow: "0 8px 40px rgba(0,0,0,0.5)",
        }}>
          {/* Header */}
          <div style={{
            padding: "14px 16px", borderBottom: "1px solid var(--line)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{
                width: 8, height: 8, borderRadius: "50%", background: "var(--moss)",
                boxShadow: "0 0 0 2px rgba(116,147,106,0.3)",
                animation: "pulse 2.4s ease-in-out infinite", display: "inline-block",
              }} />
              <span style={{ fontFamily: "'Space Mono', monospace", fontSize: 12, fontWeight: 700, color: "var(--chalk)", letterSpacing: "0.04em" }}>
                EWS Guide
              </span>
            </div>
            <button
              onClick={() => setOpen(false)}
              style={{ background: "none", border: "none", color: "var(--chalk-dim)", fontSize: 18, cursor: "pointer", lineHeight: 1, padding: "0 2px" }}
            >×</button>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: "14px 14px 6px" }}>
            {messages.map((m, i) => <Message key={i} msg={m} />)}

            {/* Quick replies — only after welcome */}
            {messages.length === 1 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
                {QUICK_REPLIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    style={{
                      padding: "5px 10px", borderRadius: 20, fontSize: 11,
                      background: "var(--panel-2)", border: "1px solid var(--line-strong)",
                      color: "var(--chalk-dim)", cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{
            padding: "10px 12px", borderTop: "1px solid var(--line)",
            display: "flex", gap: 8,
          }}>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about the system…"
              style={{
                flex: 1, background: "var(--panel-2)", border: "1px solid var(--line-strong)",
                color: "var(--chalk)", borderRadius: 8, padding: "8px 11px", fontSize: 13,
                fontFamily: "inherit",
              }}
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim()}
              style={{
                padding: "8px 14px", background: "var(--ember)", border: "none",
                borderRadius: 8, color: "#fff", fontSize: 13, fontWeight: 600,
                cursor: input.trim() ? "pointer" : "not-allowed",
                opacity: input.trim() ? 1 : 0.5,
              }}
            >
              ↑
            </button>
          </div>
        </div>
      )}

      {/* Floating button */}
      <button
        onClick={() => setOpen((v) => !v)}
        title="Help & guidance"
        style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 9991,
          width: 52, height: 52, borderRadius: "50%",
          background: open ? "var(--panel-2)" : "var(--ember)",
          border: "1px solid var(--line-strong)",
          color: "#fff", fontSize: 22, cursor: "pointer",
          boxShadow: "0 4px 20px rgba(194,75,58,0.35)",
          display: "flex", alignItems: "center", justifyContent: "center",
          transition: "background .2s, transform .15s",
          transform: open ? "rotate(45deg)" : "rotate(0deg)",
        }}
      >
        {open ? "+" : "?"}
      </button>
    </>
  );
}
