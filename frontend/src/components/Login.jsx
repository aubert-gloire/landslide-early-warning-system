import { useState, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

function Wordmark() {
  return (
    <>
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
    </>
  );
}

function Card({ children }) {
  return (
    <div style={{
      width: "100%", maxWidth: 380,
      background: "var(--panel)", border: "1px solid var(--line-strong)",
      borderRadius: 14, padding: "32px 28px",
    }}>
      {children}
    </div>
  );
}

function Label({ children }) {
  return (
    <label style={{ fontSize: 11, color: "var(--chalk-dim)", letterSpacing: "0.05em" }}>
      {children}
    </label>
  );
}

function Input(props) {
  return (
    <input
      {...props}
      style={{
        background: "var(--panel-2)", border: "1px solid var(--line-strong)",
        borderRadius: 8, padding: "11px 14px",
        color: "var(--chalk)", fontFamily: "inherit", fontSize: 14,
        outline: "none", width: "100%", boxSizing: "border-box",
      }}
    />
  );
}

function SubmitButton({ loading, disabled, children }) {
  return (
    <button
      type="submit"
      disabled={loading || disabled}
      style={{
        marginTop: 4, padding: "12px 0", borderRadius: 8, width: "100%",
        background: "var(--ember)", border: "1px solid var(--ember)",
        color: "#fff", fontFamily: "inherit", fontSize: 14, fontWeight: 600,
        cursor: loading || disabled ? "not-allowed" : "pointer",
        opacity: loading || disabled ? 0.6 : 1,
        transition: "opacity .15s",
      }}
    >
      {children}
    </button>
  );
}

function ErrorBox({ message }) {
  if (!message) return null;
  return (
    <div style={{
      padding: "10px 12px",
      background: "rgba(194,75,58,0.12)", border: "1px solid rgba(194,75,58,0.35)",
      borderRadius: 8, color: "var(--ember-text)", fontSize: 13,
    }}>
      {message}
    </div>
  );
}

// ── First-time setup screen ───────────────────────────────────────────────────

function SetupScreen({ onDone }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm]   = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (password.length < 6)  { setError("Password must be at least 6 characters."); return; }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/auth/setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Setup failed."); return; }
      onDone();
    } catch {
      setError("Cannot reach server. Check your connection.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <p style={{
        fontFamily: "'Space Mono', monospace", fontSize: 10,
        color: "var(--chalk-dim)", letterSpacing: "0.10em",
        textTransform: "uppercase", marginBottom: 6,
      }}>
        First-time setup
      </p>
      <p style={{ fontSize: 13, color: "var(--chalk-dim)", marginBottom: 22, lineHeight: 1.6 }}>
        Create your admin password. You'll use this every time you sign in.
      </p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <Label>PASSWORD</Label>
          <Input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Choose a password"
            autoFocus
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <Label>CONFIRM PASSWORD</Label>
          <Input
            type="password"
            value={confirm}
            onChange={e => setConfirm(e.target.value)}
            placeholder="Repeat password"
          />
        </div>
        <ErrorBox message={error} />
        <SubmitButton loading={loading} disabled={!password || !confirm}>
          {loading ? "Setting up…" : "Create Admin Account"}
        </SubmitButton>
      </form>
    </Card>
  );
}

// ── Login screen ──────────────────────────────────────────────────────────────

function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Login failed."); return; }
      sessionStorage.setItem("officer", JSON.stringify(data));
      onLogin(data);
    } catch {
      setError("Cannot reach server. Check your connection.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <p style={{
        fontFamily: "'Space Mono', monospace", fontSize: 10,
        color: "var(--chalk-dim)", letterSpacing: "0.10em",
        textTransform: "uppercase", marginBottom: 22,
      }}>
        Admin Sign In
      </p>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <Label>USERNAME</Label>
          <Input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            placeholder="admin"
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <Label>PASSWORD</Label>
          <Input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoComplete="current-password"
            placeholder="••••••••"
          />
        </div>
        <ErrorBox message={error} />
        <SubmitButton loading={loading} disabled={!username.trim() || !password}>
          {loading ? "Signing in…" : "Sign In"}
        </SubmitButton>
      </form>
    </Card>
  );
}

// ── Root component ────────────────────────────────────────────────────────────

export default function Login({ onLogin }) {
  const [screen, setScreen] = useState("loading"); // "loading" | "setup" | "login"

  useEffect(() => {
    fetch(`${API_BASE}/api/auth/setup-required`)
      .then(r => r.json())
      .then(d => setScreen(d.required ? "setup" : "login"))
      .catch(() => setScreen("login"));
  }, []);

  return (
    <div style={{
      minHeight: "100vh", background: "var(--ink)",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      padding: 24,
    }}>
      <Wordmark />

      {screen === "loading" && (
        <p style={{ color: "var(--chalk-dim)", fontSize: 13 }}>Connecting…</p>
      )}

      {screen === "setup" && (
        <SetupScreen onDone={() => setScreen("login")} />
      )}

      {screen === "login" && (
        <LoginScreen onLogin={onLogin} />
      )}

      <p style={{ marginTop: 28, fontSize: 11, color: "var(--chalk-dim)", textAlign: "center" }}>
        Restricted access — authorised personnel only.
      </p>
    </div>
  );
}
