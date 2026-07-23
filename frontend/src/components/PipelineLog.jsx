import { useEffect, useRef, useState } from "react";
import { getAuthToken } from "../hooks/useApi";

const BASE = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || "";

const styles = {
  container: {
    background: "var(--terminal)",
    border: "1px solid var(--line-strong)",
    borderRadius: 10,
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
    borderBottom: "1px solid var(--line)",
    background: "var(--ink)",
  },
  title: {
    fontSize: 12,
    fontWeight: 600,
    color: "var(--chalk-dim)",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    fontFamily: "'Space Mono', monospace",
  },
  tag: (done, error) => ({
    fontSize: 11,
    fontWeight: 600,
    padding: "2px 8px",
    borderRadius: 10,
    background: error ? "rgba(194,75,58,0.15)" : done ? "rgba(116,147,106,0.15)" : "rgba(108,154,181,0.15)",
    color: error ? "var(--ember-text)" : done ? "var(--moss-text)" : "var(--storm-text)",
  }),
  log: {
    flex: 1,
    overflowY: "auto",
    padding: "10px 14px",
    fontFamily: "'Space Mono', monospace",
    fontSize: 12,
    lineHeight: 1.7,
  },
  line: (type) => ({
    color: type === "done"  ? "var(--moss-text)"
         : type === "error" ? "var(--ember-text)"
         : type === "sms"   ? "var(--amber-text)"
         : "var(--chalk-dim)",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  }),
  cursor: {
    display: "inline-block",
    width: 7,
    height: 13,
    background: "var(--storm)",
    marginLeft: 2,
    animation: "blink 1s step-end infinite",
  },
};

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
  const [status, setStatus] = useState("running");
  const bottomRef = useRef(null);

  useEffect(() => {
    // EventSource can't set custom headers, so the token travels as a query
    // param here instead of the Authorization header authHeaders() uses elsewhere.
    const token = getAuthToken();
    const url = `${BASE}/api/trigger/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;
    const es = new EventSource(url);

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
                background: "none", border: "none", color: "var(--chalk-dim)",
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
