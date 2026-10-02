import { useCallback, useEffect, useState } from "react";
import { DEFAULT_LOG_TAIL, fetchServiceLogs } from "./api";

const TAIL_CHOICES = [50, 100, 200, 500] as const;

/** Container stdout/stderr snapshot for one Compose service. */
export function ServiceLogs(props: { service: string }) {
  const [tail, setTail] = useState<number>(DEFAULT_LOG_TAIL);
  const [text, setText] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = await fetchServiceLogs(props.service, tail);
      setText(payload.text);
    } catch (err) {
      setText(null);
      setError(err instanceof Error ? err.message : "Failed to load logs.");
    } finally {
      setBusy(false);
    }
  }, [props.service, tail]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Logs</h2>
        <div className="logs-controls">
          <label className="logs-tail">
            Tail
            <select
              value={tail}
              disabled={busy}
              onChange={(e) => setTail(Number(e.target.value))}
            >
              {TAIL_CHOICES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={`refresh${busy ? " is-loading" : ""}`}
            disabled={busy}
            aria-busy={busy}
            onClick={() => void load()}
          >
            {busy ? (
              <span className="spinner refresh-spinner" aria-hidden="true" />
            ) : null}
            Refresh
          </button>
        </div>
      </div>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {busy && text === null && !error ? (
        <div className="logs-loading" role="status" aria-busy="true">
          <span className="spinner refresh-spinner" aria-hidden="true" />
          <span>Loading logs…</span>
        </div>
      ) : null}
      {text !== null ? (
        <pre className="logs-pre">{text || "(no log output)"}</pre>
      ) : null}
    </section>
  );
}
