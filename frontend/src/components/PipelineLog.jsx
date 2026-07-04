import { useEffect, useRef, useState } from "react";

const BASE = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || "";

const styles = {
  container: {
    background: "#0a0e1a",
    border: "1px solid #1e293b",
    borderRadius: 8,
    display: "flex",
    flexDirection: "column",
    height: 260,
    overflow: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "8px 14px",
    borderBottom: "1px solid #1e293b",
    background: "#0f1117",
  },
  title: {
    fontSize: 12,
    fontWeight: 600,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    fontFamily: "monospace",
  },
  tag: (done, error) => ({
    fontSize: 11,
    fontWeight: 600,
    padding: "2px 8px",
    borderRadius: 10,
    background: error ? "#450a0a" : done ? "#14532d" : "#1e3a5f",
    color: error ? "#fca5a5" : done ? "#86efac" : "#93c5fd",
  }),
  log: {
    flex: 1,
    overflowY: "auto",
    padding: "10px 14px",
    fontFamily: "monospace",
    fontSize: 12,
    lineHeight: 1.7,
  },
  line: (type) => ({
    color: type === "done"  ? "#86efac"
         : type === "error" ? "#fca5a5"
         : type === "sms"   ? "#fcd34d"
         : "#94a3b8",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  }),
  cursor: {
    display: "inline-block",
    width: 7,
    height: 13,
    background: "#3b82f6",
    marginLeft: 2,
    animation: "blink 1s step-end infinite",
  },
};

// inject blink keyframe once
if (typeof document !== "undefined" && !document.getElementById("blink-style")) {
  const s = document.createElement("style");
  s.id = "blink-style";
  s.textContent = "@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }";
  document.head.appendChild(s);
}

function lineType(text) {
  if (text.includes("SMS →")) return "sms";
  if (text.includes("complete") || text.includes("Done")) return "done";
  if (text.includes("Error") || text.includes("error")) return "error";
  return "log";
}

export default function PipelineLog({ onDone, onClose }) {
  const [lines, setLines] = useState([]);
  const [status, setStatus] = useState("running"); // running | done | error
  const bottomRef = useRef(null);

  useEffect(() => {
    const es = new EventSource(`${BASE}/api/trigger/stream`);

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.type === "log") {
        setLines((prev) => [...prev, event.message]);
      } else if (event.type === "done") {
        const summary = event.result;
        setLines((prev) => [
          ...prev,
          `✓ Pipeline complete — ${summary.units_processed} units scored, `
          + `${summary.alerts_triggered} alerts triggered, ${summary.sms_sent} SMS sent`,
        ]);
        setStatus("done");
        es.close();
        if (onDone) onDone(summary);
      } else if (event.type === "error") {
        setLines((prev) => [...prev, `✗ Error: ${event.message}`]);
        setStatus("error");
        es.close();
      }
    };

    es.onerror = () => {
      setLines((prev) => [...prev, "✗ Stream connection lost"]);
      setStatus("error");
      es.close();
    };

    return () => es.close();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.title}>Pipeline Log</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={styles.tag(status === "done", status === "error")}>
            {status === "running" ? "Running…" : status === "done" ? "Complete" : "Error"}
          </span>
          {status !== "running" && (
            <button
              onClick={onClose}
              style={{
                background: "none", border: "none", color: "#475569",
                cursor: "pointer", fontSize: 16, lineHeight: 1, padding: "0 2px",
              }}
            >×</button>
          )}
        </div>
      </div>
      <div style={styles.log}>
        {lines.map((line, i) => (
          <div key={i} style={styles.line(lineType(line))}>{line}</div>
        ))}
        {status === "running" && <span style={styles.cursor} />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
