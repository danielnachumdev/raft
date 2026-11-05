/**
 * Persistence stance (#249): browser-local for v1.
 * Overview → `raft-serve-trends-dashboards`; service → `raft-serve-service-trends`.
 * A later hybrid under `~/.raft/` can implement this adapter without shell changes.
 */
export type PersistenceAdapter<T> = {
  load: () => T;
  save: (value: T) => void;
};

/** localStorage adapter; corrupt / quota failures never throw to callers. */
export function createLocalStorageAdapter<T>(opts: {
  key: string;
  parse: (raw: unknown) => T | null;
  fallback: () => T;
}): PersistenceAdapter<T> {
  const { key, parse, fallback } = opts;
  return {
    load: () => {
      try {
        if (typeof localStorage === "undefined") return fallback();
        const raw = localStorage.getItem(key);
        if (raw === null) return fallback();
        return parse(JSON.parse(raw)) ?? fallback();
      } catch {
        return fallback();
      }
    },
    save: (value) => {
      try {
        if (typeof localStorage === "undefined") return;
        localStorage.setItem(key, JSON.stringify(value));
      } catch {
        /* ignore */
      }
    },
  };
}
