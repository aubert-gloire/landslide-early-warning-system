import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
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
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", background: "var(--ink)",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
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
        width: "100%", maxWidth: 380,
        background: "var(--panel)", border: "1px solid var(--line-strong)",
        borderRadius: 14, padding: "32px 28px",
      }}>
        <p style={{
          fontFamily: "'Space Mono', monospace", fontSize: 10,
          color: "var(--chalk-dim)", letterSpacing: "0.10em",
          textTransform: "uppercase", marginBottom: 22,
        }}>
          Admin Sign In
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "var(--chalk-dim)", letterSpacing: "0.05em" }}>
              USERNAME
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              placeholder="admin"
              style={{
                background: "var(--panel-2)", border: "1px solid var(--line-strong)",
                borderRadius: 8, padding: "11px 14px",
                color: "var(--chalk)", fontFamily: "inherit", fontSize: 14,
                outline: "none",
              }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "var(--chalk-dim)", letterSpacing: "0.05em" }}>
              PASSWORD
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder="••••••••"
              style={{
                background: "var(--panel-2)", border: "1px solid var(--line-strong)",
                borderRadius: 8, padding: "11px 14px",
                color: "var(--chalk)", fontFamily: "inherit", fontSize: 14,
                outline: "none",
              }}
            />
          </div>

          {error && (
            <div style={{
              padding: "10px 12px",
              background: "rgba(194,75,58,0.12)", border: "1px solid rgba(194,75,58,0.35)",
              borderRadius: 8, color: "var(--ember-text)", fontSize: 13,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password}
            style={{
              marginTop: 4,
              padding: "12px 0", borderRadius: 8,
              background: "var(--ember)", border: "1px solid var(--ember)",
              color: "#fff", fontFamily: "inherit", fontSize: 14, fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading || !username.trim() || !password ? 0.6 : 1,
              transition: "opacity .15s",
            }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>

      <p style={{ marginTop: 28, fontSize: 11, color: "var(--chalk-dim)", textAlign: "center" }}>
        Restricted access — authorised personnel only.
      </p>
    </div>
  );
}
