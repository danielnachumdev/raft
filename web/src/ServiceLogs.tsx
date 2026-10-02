import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_LOG_TAIL, fetchServiceLogs } from "./api";
import { LogLines } from "./LogLines";
import { filterLogLines, parseLogText } from "./logParse";

const TAIL_CHOICES = [50, 100, 200, 500] as const;

/** Container stdout/stderr snapshot for one Compose service. */
export function ServiceLogs(props: { service: string }) {
  const [tail, setTail] = useState<number>(DEFAULT_LOG_TAIL);
  const [text, setText] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);

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

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [expanded]);

  const lines = useMemo(
    () => (text === null ? [] : parseLogText(text)),
    [text],
  );
  const visible = useMemo(() => filterLogLines(lines, query), [lines, query]);

  const body = (
    <>
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
        <>
          <label className="logs-search">
            <span className="logs-search-label">Filter</span>
            <input
              type="search"
              value={query}
              placeholder="Search logs…"
              onChange={(e) => setQuery(e.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
            {query.trim() ? (
              <span className="logs-match-count muted">
                {visible.length}/{lines.length}
              </span>
            ) : null}
          </label>
          <div className="logs-view">
            <LogLines
              lines={visible}
              query={query}
              emptyLabel={
                query.trim()
                  ? "No lines match this filter."
                  : "(no log output)"
              }
            />
          </div>
        </>
      ) : null}
    </>
  );

  const controls = (
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
      <button
        type="button"
        className="action-btn"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? "Collapse" : "Expand"}
      </button>
    </div>
  );

  if (expanded) {
    return (
      <>
        <section className="panel logs-panel logs-panel-placeholder" aria-hidden="true">
          <div className="panel-head">
            <h2>Logs</h2>
          </div>
        </section>
        <div
          className="logs-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={`Logs for ${props.service}`}
        >
          <div className="logs-overlay-panel">
            <div className="panel-head">
              <h2>Logs — {props.service}</h2>
              {controls}
            </div>
            {body}
            <p className="logs-overlay-hint muted">Press Esc to collapse</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <section className="panel logs-panel">
      <div className="panel-head">
        <h2>Logs</h2>
        {controls}
      </div>
      {body}
    </section>
  );
}
