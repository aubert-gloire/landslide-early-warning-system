import { useState, useEffect, useCallback } from "react";

const BASE = import.meta.env.VITE_API_BASE_URL || "";

export function useApi(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BASE}${path}`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
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
