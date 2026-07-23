import { useState, useEffect, useCallback } from "react";

const BASE = import.meta.env.VITE_API_BASE_URL || "";
const MAX_RETRIES = 4;
const RETRY_DELAYS = [2000, 5000, 10000, 20000]; // ms — handles Render cold-start (~30s)

// Every protected route requires this token (backend/app/routes/auth.py:require_auth).
// Stored in sessionStorage by Login.jsx on login/guest entry.
export function getAuthToken() {
  try {
    const officer = JSON.parse(sessionStorage.getItem("officer") || "null");
    return officer?.token ?? null;
  } catch {
    return null;
  }
}

export function authHeaders(extra = {}) {
  const token = getAuthToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

export function useApi(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    setError(null);
    let lastError = null;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
        if (res.status === 401) {
          // Bad/expired token — retrying won't help, fail immediately instead of
          // burning ~37s through the full retry backoff.
          throw Object.assign(new Error("Session expired — please sign in again."), { fatal: true });
        }
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        setData(await res.json());
        setLoading(false);
        return;
      } catch (e) {
        lastError = e;
        if (e.fatal) break;
        if (attempt < MAX_RETRIES) {
          await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt]));
        }
      }
    }
    setError(lastError.message);
    setLoading(false);
  }, [path]);

  useEffect(() => { fetch_(); }, [fetch_, ...deps]);
  return { data, loading, error, refetch: fetch_ };
}

export async function triggerPipeline(overrides = {}) {
  const res = await fetch(`${BASE}/api/trigger`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(overrides),
  });
  if (!res.ok) throw new Error(`Trigger failed: ${res.status}`);
  return res.json();
}
