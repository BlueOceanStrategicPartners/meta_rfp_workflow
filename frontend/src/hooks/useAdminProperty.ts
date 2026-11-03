import { useCallback, useEffect, useState } from "react";

const KEY = "rfp-admin-property";

function readStored(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function writeStored(id: string | null) {
  try {
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
}

/**
 * Selected property for Inventory / Occupancy, remembered in localStorage.
 * Falls back to the first property when the stored one no longer exists.
 */
export function useAdminProperty(properties: { id: string }[] | null | undefined) {
  const [id, setIdState] = useState<string | null>(() => readStored());

  useEffect(() => {
    if (!properties) return;
    if (properties.length === 0) {
      if (id !== null) setIdState(null);
      return;
    }
    if (!id || !properties.some((p) => p.id === id)) {
      setIdState(properties[0].id);
      writeStored(properties[0].id);
    }
  }, [properties, id]);

  const setId = useCallback((next: string) => {
    setIdState(next);
    writeStored(next);
  }, []);

  // Until the list loads, don't hand out a stored id that may be stale.
  const valid = properties ? (properties.some((p) => p.id === id) ? id : null) : null;
  return [valid, setId] as const;
}
