import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

const OFFICERS = [
  { username: "gakenke", label: "Gakenke",  role: "Field Officer" },
  { username: "burera",  label: "Burera",   role: "Field Officer" },
  { username: "musanze", label: "Musanze",  role: "Field Officer" },
  { username: "gicumbi", label: "Gicumbi",  role: "Field Officer" },
  { username: "admin",   label: "Admin",    role: "System Admin"  },
];

export default function Login({ onLogin }) {
  const [loading, setLoading] = useState(null); // username being loaded
  const [error, setError]     = useState("");

  async function handleLogin(username) {
    setLoading(username);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Login failed.");
        return;
      }
      sessionStorage.setItem("officer", JSON.stringify(data));
      onLogin(data);
    } catch {
      setError("Cannot reach server. Check your connection.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", background: "var(--ink)",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: 24,
    }}>
      {/* Wordmark */}
      <div style={{
        fontFamily: "'Space Mono', monospace", fontWeight: 700, fontSize: 20,
        letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 10,
        marginBottom: 8,
      }}>
        <span style={{
          width: 9, height: 9, borderRadius: "50%", background: "var(--ember)",
          boxShadow: "0 0 0 3px rgba(194,75,58,0.25)",
          animation: "pulse 2.4s ease-in-out infinite", display: "inline-block",
        }} />
        Landslide EWS
      </div>
      <p style={{ color: "var(--chalk-dim)", fontSize: 13, marginBottom: 40, letterSpacing: "0.03em" }}>
        Rwanda Northern Province — Early Warning System
      </p>

      {/* Card */}
      <div style={{
        width: "100%", maxWidth: 400,
        background: "var(--panel)", border: "1px solid var(--line-strong)",
        borderRadius: 14, padding: "28px 24px",
      }}>

        {/* District Officers */}
        <p style={{
          fontFamily: "'Space Mono', monospace", fontSize: 10,
          color: "var(--chalk-dim)", letterSpacing: "0.10em",
          textTransform: "uppercase", marginBottom: 14,
        }}>
          District Officers
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
          {OFFICERS.filter(o => o.username !== "admin").map((o) => (
            <button
              key={o.username}
              onClick={() => handleLogin(o.username)}
              disabled={loading !== null}
              style={{
                padding: "12px 10px", borderRadius: 8,
                background: loading === o.username ? "rgba(108,154,181,0.2)" : "var(--panel-2)",
                border: loading === o.username ? "1px solid var(--storm)" : "1px solid var(--line-strong)",
                color: loading === o.username ? "var(--storm-text)" : "var(--chalk)",
                fontFamily: "inherit", fontSize: 14, fontWeight: 600, cursor: "pointer",
                display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2,
                opacity: loading !== null && loading !== o.username ? 0.5 : 1,
                transition: "all .15s",
              }}
            >
              <span>{loading === o.username ? "Signing in…" : o.label}</span>
              <span style={{ fontSize: 10, color: "var(--chalk-dim)", fontWeight: 400 }}>{o.role}</span>
            </button>
          ))}
        </div>

        {/* Admin — full width */}
        <button
          onClick={() => handleLogin("admin")}
          disabled={loading !== null}
          style={{
            width: "100%", padding: "11px 14px", borderRadius: 8, marginBottom: 20,
            background: loading === "admin" ? "rgba(108,154,181,0.2)" : "var(--panel-2)",
            border: loading === "admin" ? "1px solid var(--storm)" : "1px solid var(--line-strong)",
            color: loading === "admin" ? "var(--storm-text)" : "var(--chalk)",
            fontFamily: "inherit", fontSize: 14, fontWeight: 600, cursor: "pointer",
            display: "flex", justifyContent: "space-between", alignItems: "center",
            opacity: loading !== null && loading !== "admin" ? 0.5 : 1,
            transition: "all .15s",
          }}
        >
          <span>{loading === "admin" ? "Signing in…" : "System Admin"}</span>
          <span style={{ fontSize: 11, color: "var(--chalk-dim)", fontWeight: 400 }}>All districts</span>
        </button>

        {/* Divider */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
          <div style={{ flex: 1, height: 1, background: "var(--line-strong)" }} />
          <span style={{ fontSize: 11, color: "var(--chalk-dim)", fontFamily: "'Space Mono', monospace" }}>or</span>
          <div style={{ flex: 1, height: 1, background: "var(--line-strong)" }} />
        </div>

        {/* Guest */}
        <button
          onClick={() => handleLogin("guest")}
          disabled={loading !== null}
          style={{
            width: "100%", padding: "12px 0", borderRadius: 8,
            background: "transparent",
            border: "1px solid var(--line-strong)",
            color: "var(--chalk-dim)", fontFamily: "inherit", fontSize: 14,
            cursor: "pointer", letterSpacing: "0.02em",
            opacity: loading !== null && loading !== "guest" ? 0.5 : 1,
            transition: "all .15s",
          }}
        >
          {loading === "guest" ? "Entering…" : "Continue as Guest →"}
        </button>

        {error && (
          <div style={{
            marginTop: 14, padding: "10px 12px",
            background: "rgba(194,75,58,0.12)", border: "1px solid rgba(194,75,58,0.35)",
            borderRadius: 8, color: "var(--ember-text)", fontSize: 13,
          }}>
            {error}
          </div>
        )}
      </div>

      <p style={{ marginTop: 28, fontSize: 11, color: "var(--chalk-dim)", textAlign: "center", maxWidth: 380, lineHeight: 1.7 }}>
        Restricted access — authorised district officers only.<br />
        Guest access is read-only for demonstration purposes.
      </p>
    </div>
  );
}
