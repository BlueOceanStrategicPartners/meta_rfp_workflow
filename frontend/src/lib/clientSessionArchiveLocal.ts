const LOCAL_ARCHIVE_KEY = "rfp-client-session-archived";

function readLocalArchiveMap(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(LOCAL_ARCHIVE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    const out: Record<string, boolean> = {};
    for (const [id, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof id === "string" && id && value) out[id] = true;
    }
    return out;
  } catch {
    return {};
  }
}

function writeLocalArchiveMap(map: Record<string, boolean>) {
  try {
    localStorage.setItem(LOCAL_ARCHIVE_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export function getLocalArchivedFlag(sessionId: string): boolean | undefined {
  const map = readLocalArchiveMap();
  return map[sessionId] ? true : undefined;
}

/** Local fallback only tracks ids archived offline (value is always true when present). */
export function setLocalArchivedFlag(sessionId: string, archived: boolean) {
  const map = readLocalArchiveMap();
  if (archived) {
    map[sessionId] = true;
  } else {
    delete map[sessionId];
  }
  writeLocalArchiveMap(map);
}

export function mergeLocalArchivedIntoSummaries<T extends { id: string; archived?: boolean }>(
  sessions: T[],
): T[] {
  const map = readLocalArchiveMap();
  if (!Object.keys(map).length) return sessions;
  return sessions.map((s) => {
    if (!(s.id in map)) return s;
    if (s.archived === false) {
      clearLocalArchivedFlag(s.id);
      return s;
    }
    return { ...s, archived: true };
  });
}

export function clearLocalArchivedFlag(sessionId: string) {
  setLocalArchivedFlag(sessionId, false);
}
