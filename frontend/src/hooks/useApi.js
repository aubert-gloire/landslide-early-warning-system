import { useState, useEffect, useCallback } from "react";

const BASE = import.meta.env.VITE_API_BASE_URL || "";
const MAX_RETRIES = 4;
const RETRY_DELAYS = [2000, 5000, 10000, 20000]; // ms — handles Render cold-start (~30s)

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
        const res = await fetch(`${BASE}${path}`);
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        setData(await res.json());
        setLoading(false);
        return;
      } catch (e) {
        lastError = e;
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(overrides),
  });
  if (!res.ok) throw new Error(`Trigger failed: ${res.status}`);
  return res.json();
}
