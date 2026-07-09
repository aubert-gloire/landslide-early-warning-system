import { useState, useEffect, useRef } from "react";

const BOT_NAME = "EWS Guide";

const WELCOME = `Hello! I'm the EWS Guide — I can explain how this system works and help you use it.\n\nTry a quick question below or type your own.`;

const QA = [
  {
    triggers: ["how does it work", "how does the system work", "explain the system", "overview", "what does this system do", "how does ews work"],
    answer: `Every morning at 06:00 Kigali time, the system runs automatically:\n\n1. RAINFALL — NASA satellites measure how much rain fell across Northern Province yesterday. The data arrives with ~14 hours delay via GPM IMERG. If satellite data isn't ready, it falls back to CHIRPS (4-day lag).\n\n2. SCORING — Northern Province is divided into 396 slope units (sections of hillside). For each one, the system combines rainfall + slope angle + soil type + vegetation cover and runs it through an XGBoost model. Every slope unit gets a risk score from 0–100%.\n\n3. ALERTING — Any slope unit above the alert threshold triggers a warning. The system finds the registered officer for that district and sends an SMS through two providers simultaneously (Africa's Talking + Telerivet).\n\n4. RESPONSE — The officer replies YES or NO by SMS. That feedback is logged on the Alerts tab.\n\nThe dashboard shows a live risk map, district summary cards, rainfall gauges, and the full SMS log.`,
  },
  {
    triggers: ["risk map", "map", "colour", "color", "polygon", "what do the colours", "what do colors mean"],
    answer: `The Risk Map shows all 396 slope units in Northern Province as coloured polygons:\n\nGreen — low risk (below 50%)\nAmber — moderate risk (50–79%)\nRed — high risk (80%+) — SMS alert dispatched\n\nClick any polygon to see the unit ID, district, sector, risk %, and whether an alert was sent.\n\nThe map legend shows:\n• Assessment date — when the pipeline last ran\n• Rainfall data to — the date of the most recent rainfall data used\n\nNote: the map always shows the most recent pipeline results. Run the pipeline to refresh it with today's data.`,
  },
  {
    triggers: ["pipeline", "run pipeline", "what is pipeline", "trigger", "cron", "schedule", "daily", "what does pipeline do"],
    answer: `The pipeline is the core process that runs every morning. Click "Run Pipeline" in the top-right to trigger it manually.\n\nWhat it does step by step:\n1. Downloads yesterday's rainfall from NASA GPM IMERG (~14h lag). Falls back to CHIRPS if IMERG isn't ready.\n2. Checks USGS earthquake data — if a M4.0+ earthquake occurred within 200km in the last 48 hours, the alert threshold is lowered automatically.\n3. Builds a feature matrix combining rainfall + terrain data for all 396 slope units.\n4. Runs XGBoost inference — scores every slope unit.\n5. Saves all predictions to the database.\n6. Sends SMS alerts to field officers for any unit above the threshold.\n\nIt also runs automatically at 10:00 AM Kigali time daily via GitHub Actions.`,
  },
  {
    triggers: ["alert", "sms", "send alert", "dispatch", "officer", "expert", "when are alerts sent", "who gets the sms"],
    answer: `SMS alerts are sent automatically during the pipeline when any slope unit exceeds the risk threshold.\n\nEach SMS includes:\n• District and sector of the high-risk slope unit\n• Risk level (WATCH / WARNING / EMERGENCY)\n• Risk percentage\n• GPS coordinates of the highest-risk point\n• The main driver (e.g. "antecedent 5day mm")\n• Instructions: reply YES [unit_id] to confirm or NO [unit_id] to dispute\n\nAlerts go through two providers simultaneously — Africa's Talking and Telerivet (Android SIM route) — to guarantee delivery on MTN Rwanda.\n\nYou can also send a manual alert from the Predict panel using real field measurements.`,
  },
  {
    triggers: ["seismic", "earthquake", "usgs", "tremor", "quake", "threshold lower"],
    answer: `The system monitors earthquake activity near Northern Province via the USGS Earthquake API (free, checked on every pipeline run).\n\nIf a magnitude 4.0+ earthquake is detected within 200km of Northern Province in the last 48 hours, the alert threshold is automatically lowered from the default 5% to 3%. This means more slope units receive alerts during seismically active periods — because earthquakes loosen soil and make slopes more vulnerable to rainfall-triggered failure.\n\nThe pipeline log shows whether seismic activity was detected and what threshold was used for that run.`,
  },
  {
    triggers: ["slope unit", "what is a slope unit", "unit", "396", "terrain unit", "hydrological", "what is a unit"],
    answer: `A slope unit is a section of hillside that behaves as a single landslide risk area — bounded by ridge lines and valley lines, draining water in one consistent direction.\n\nThe system monitors 396 slope units across Northern Province. Each one is mapped as a polygon derived from the Copernicus 30m elevation model.\n\nWhy slope units? A pixel-based grid treats flat land and steep cliffs the same way. Slope units group terrain that physically behaves together under rainfall, which is more meaningful for landslide prediction. This approach follows Kuradusenge et al. (2020), who mapped Northern Province specifically.`,
  },
  {
    triggers: ["predict", "prediction", "run prediction", "feature", "input", "how to use predict", "predict panel"],
    answer: `The Predict panel lets you run the XGBoost model against any input values — useful for testing scenarios or dispatching a manual alert.\n\n1. Choose a preset (high / medium / low risk) or fill in values manually.\n2. Required: slope angle, daily rainfall, 3-day and 5-day antecedent rainfall.\n3. Click "Run Prediction" — you get a risk %, risk level, top driving features, and a plain-language explanation.\n4. To send a manual SMS: fill in the district name and click "Send SMS Alert". Use "Force Send" to override the threshold if you have additional field context.`,
  },
  {
    triggers: ["district", "districts", "gakenke", "burera", "musanze", "gicumbi", "district card", "district tab"],
    answer: `The Districts tab shows a summary card for each of the 4 monitored districts:\n\n• Peak risk today — highest risk score among all slope units in that district\n• Slope units monitored — total units tracked in that district\n• Alerts (last 7 days) — SMS alerts sent recently\n• Highest-risk sector — the sector name within the district carrying the most risk\n\nCards update automatically after every pipeline run.`,
  },
  {
    triggers: ["data source", "where does the data", "rainfall data", "satellite", "imerg", "chirps", "gpm", "nasa"],
    answer: `Rainfall (primary): GPM IMERG Late Daily — NASA satellite rainfall, available ~14 hours after the day ends. Authenticated via NASA Earthdata.\n\nRainfall (fallback): CHIRPS v2 Preliminary — UC Santa Barbara product, ~4-day lag. Used when IMERG isn't yet available for the target date.\n\nTerrain: Copernicus 30m DEM — slope angle, aspect, Topographic Wetness Index.\n\nVegetation: Sentinel-2 NDVI via Google Earth Engine.\n\nSoil: ISRIC SoilGrids — soil class per slope unit.\n\nSeismic: USGS Earthquake Hazards Program API — free, no auth, queried on every pipeline run.\n\nSMS delivery: Africa's Talking + Telerivet (parallel dispatch).`,
  },
  {
    triggers: ["model", "xgboost", "machine learning", "ai", "accuracy", "auc", "how accurate", "train", "how was the model trained"],
    answer: `The model is XGBoost — a gradient boosting algorithm trained on historical rainfall and terrain data for Northern Province Rwanda.\n\nTraining pipeline: SimpleImputer → SMOTE oversampling → XGBClassifier, run inside a 5-fold cross-validation so no data leaks between folds.\n\nPerformance:\n• AUC: 0.959 (best among 4 models tested)\n• False Negative Rate: 8.3% at production threshold\n• Production threshold: 5% — set low to minimise missed real events\n\nTop features by importance:\n1. 5-day antecedent rainfall (46%)\n2. 3-day antecedent rainfall (33%)\n3. Daily rainfall (5%)\n\nXGBoost outperformed Random Forest, Logistic Regression, and SVM on this dataset.`,
  },
  {
    triggers: ["antecedent", "3-day", "5-day", "10-day", "prior rainfall", "what is antecedent", "cumulative", "soil saturation"],
    answer: `Antecedent rainfall is how much rain fell in the days before today — it tells the model how saturated the soil already is before a new storm arrives.\n\n• 3-day total — shallow soil saturation. High values mean surface layers are already wet.\n• 5-day total — the single most important feature in the model (46% importance). Critical level: above 150mm.\n• 10-day total — indicates deeper clay layer saturation.\n\nThe key insight: a 30mm storm on soil that already received 120mm in the past week is far more dangerous than 30mm on dry ground. Antecedent rainfall captures this.`,
  },
  {
    triggers: ["twi", "topographic wetness", "ndvi", "vegetation index", "what is twi", "what is ndvi"],
    answer: `TWI (Topographic Wetness Index) — measures where water naturally collects based on slope steepness and how much land drains into a point. A high TWI means water funnels there from uphill.\n• Critical level: TWI above 12.\n• Derived from the Copernicus 30m elevation model.\n\nNDVI (Normalised Difference Vegetation Index) — measures vegetation density from Sentinel-2 satellite imagery. Range is -1 to 1.\n• Below 0.35: sparse vegetation, low root cohesion, higher failure risk.\n• Why it matters: roots hold soil together. Deforested or degraded hillsides lose this mechanical anchor and fail more easily under rainfall.`,
  },
  {
    triggers: ["threshold", "5%", "percent", "what is the threshold", "alert threshold", "why 5"],
    answer: `The alert threshold is 5% probability.\n\nIf the model gives any slope unit a 5% or higher chance of landslide, an SMS is sent. This is intentionally low — in life-safety systems, it is better to send more alerts (some false alarms) than to miss a real event.\n\nThe map uses different visual thresholds for clarity:\n• Green: below 50%\n• Amber: 50–79%\n• Red: 80%+\n\nBut the SMS fires at 5%+, well below what shows as red on the map. After an earthquake is detected, the threshold drops further to 3%.`,
  },
  {
    triggers: ["log", "pipeline log", "cache hit", "0 units", "zero alerts", "no alert", "what does it mean", "stream", "pipeline message"],
    answer: `The pipeline log streams live as the run progresses. Key messages:\n\n"MongoDB cache hit" — rainfall data already saved from an earlier run today, skipping the download step.\n"IMERG success" — NASA satellite rainfall downloaded for all 396 units.\n"Falling back to CHIRPS" — IMERG not yet available, using the backup source.\n"No seismic activity detected" — USGS check passed, using default threshold.\n"Seismic alert" — earthquake found nearby, threshold lowered for this run.\n"0 units above threshold" — no high-risk areas today. Normal during dry season. Not an error.\n"Pipeline complete" — finished. Risk map and district cards are now updated.`,
  },
  {
    triggers: ["feedback", "confirm", "denied", "reply", "officer feedback", "sms reply", "yes no"],
    answer: `After receiving an SMS alert, field officers reply by text:\n• Reply "YES [unit_id]" to confirm conditions on the ground match the alert\n• Reply "NO [unit_id]" to report the alert was a false alarm\n\nFeedback appears in the Alerts tab and contributes to the system's real-world accuracy tracking over time. The confirmation rate — confirmed alerts divided by total alerts — is the operational accuracy measure.`,
  },
  {
    triggers: ["alerts tab", "alert table", "alert history", "view alerts", "past alerts", "filter", "how to see alerts"],
    answer: `The Alerts tab shows every SMS dispatched by the system.\n\n• Filter by district using the dropdown.\n• The stats panel at the top shows totals: alerts sent, confirmed, denied, awaiting feedback, confirmation rate.\n\nColumn meanings:\n• Sent at — date and time\n• Unit ID — slope unit that triggered the alert\n• Risk % — model score at the time\n• Status — SMS delivery result (sent / delivered / failed)\n• Officer Feedback — YES/NO reply received`,
  },
  {
    triggers: ["why northern province", "why 4 districts", "why not all rwanda", "coverage", "which area", "scope"],
    answer: `The system covers Northern Province — Gakenke, Burera, Musanze, and Gicumbi — for three reasons:\n\n1. Highest risk: Northern Province has Rwanda's highest historical landslide rate, driven by steep volcanic slopes and heavy seasonal rainfall.\n\n2. Calibrated model: the training data (Kuradusenge et al., 2020) was built specifically for this region. The model's thresholds are calibrated to Northern Province soils, slopes, and rainfall patterns — not Rwanda as a whole.\n\n3. MINEMA priority: Rwanda's national disaster authority has designated Northern Province as the primary landslide early warning zone.\n\nExpanding to other provinces would require region-specific training data and retraining.`,
  },
  {
    triggers: ["login", "sign in", "credentials", "account", "who can", "how do i log in"],
    answer: `On the login page, click your district button (Gakenke, Burera, Musanze, Gicumbi) or System Admin. No password required — the button identifies you as the registered officer for that district.\n\nTo access without identifying yourself, click "Continue as Guest".\n\nAll roles have identical access to every tab and feature. The district shown in the header is for identification in the SMS log — it does not restrict what you can view or do.\n\nSessions last 24 hours. Close the browser tab or click "Sign out" to end your session early.`,
  },
  {
    triggers: ["what does this not do", "limitations", "what can't it do", "does not", "limitation", "not replace"],
    answer: `What the system does NOT do:\n\n• It does not replace MINEMA or Meteo Rwanda — all alerts are decision support, not orders to evacuate.\n• It does not predict the exact location a landslide will occur — only which slope units carry elevated risk.\n• It does not have ground-level rain gauges — it uses satellite estimates with a ~14 hour delay.\n• It does not cover all of Rwanda — only Northern Province (4 districts).\n• It was trained on 12 confirmed landslide events — a real operational model would need hundreds.`,
  },
];

const FALLBACK = `I'm not sure about that. Try asking:\n\n• How does the system work?\n• What does the pipeline do?\n• What is a slope unit?\n• How does the risk map work?\n• When are SMS alerts sent?\n• What data sources does it use?\n• How accurate is the model?\n• What does the system not do?`;

const QUICK_REPLIES = [
  "How does the system work?",
  "What does the pipeline do?",
  "What is a slope unit?",
  "When are SMS alerts sent?",
  "How accurate is the model?",
  "What data sources does it use?",
  "What does the system not do?",
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
