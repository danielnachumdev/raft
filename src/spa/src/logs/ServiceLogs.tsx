import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DownloadMenu } from "../export/DownloadMenu";
import { logsDownloadUrl } from "../export/urls";
import {
  DEFAULT_LOG_TAIL,
  fetchServiceLogs,
  openServiceLogsFollow,
} from "../shared/api";
import { LogLines } from "./LogLines";
import { filterLogLines, parseLogText } from "./logParse";

const TAIL_CHOICES = [50, 100, 200, 500] as const;
const NEAR_BOTTOM_PX = 48;

/** Live-ish container logs (CLI ``raft logs -f`` via SSE); Follow on by default. */
export function ServiceLogs(props: { service: string }) {
  const [tail, setTail] = useState<number>(DEFAULT_LOG_TAIL);
  const [follow, setFollow] = useState(true);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [stick, setStick] = useState(true);
  const [epoch, setEpoch] = useState(0);
  const viewRef = useRef<HTMLDivElement>(null);

  const resubscribe = useCallback(() => {
    setEpoch((n) => n + 1);
  }, []);

  useEffect(() => {
    if (follow) return;
    let cancelled = false;
    setBusy(true);
    setError(null);
    void fetchServiceLogs(props.service, tail)
      .then((payload) => {
        if (!cancelled) setText(payload.text);
      })
      .catch((err) => {
        if (!cancelled) {
          setText("");
          setError(err instanceof Error ? err.message : "Failed to load logs.");
        }
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [follow, props.service, tail, epoch]);

  useEffect(() => {
    if (!follow) return;
    const ac = new AbortController();
    setBusy(true);
    setError(null);
    setText("");
    void runFollow(props.service, tail, ac.signal, {
      onLine: (line) => setText((prev) => (prev ? `${prev}\n${line}` : line)),
      onReady: () => setBusy(false),
      onError: (msg) => {
        setError(msg);
        setBusy(false);
      },
    });
    return () => ac.abort();
  }, [follow, props.service, tail, epoch]);

  useEffect(() => {
    const el = viewRef.current;
    if (!el || !stick) return;
    el.scrollTop = el.scrollHeight;
  }, [text, stick, query]);

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

  const lines = useMemo(() => parseLogText(text), [text]);
  const visible = useMemo(() => filterLogLines(lines, query), [lines, query]);
  const connecting = busy && text === "" && !error;

  const body = (
    <>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {connecting ? (
        <div className="logs-loading" role="status" aria-busy="true">
          <span className="spinner refresh-spinner" aria-hidden="true" />
          <span>{follow ? "Connecting…" : "Loading logs…"}</span>
        </div>
      ) : null}
      {text !== "" || (!busy && !error) ? (
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
          <div
            className="logs-view"
            ref={viewRef}
            onScroll={(e) => setStick(isNearBottom(e.currentTarget))}
          >
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
      <label className="logs-follow">
        <input
          type="checkbox"
          checked={follow}
          onChange={(e) => setFollow(e.target.checked)}
        />
        Follow
      </label>
      <label className="logs-tail">
        Tail
        <select
          value={tail}
          disabled={busy && text === ""}
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
        disabled={busy && text === ""}
        aria-busy={busy}
        onClick={resubscribe}
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
      <DownloadMenu
        kind="logs"
        hrefFor={(formatId) => logsDownloadUrl(props.service, formatId, tail)}
        disabled={Boolean(error)}
      />
    </div>
  );

  if (expanded) {
    return (
      <>
        <section
          className="panel logs-panel logs-panel-placeholder"
          aria-hidden="true"
        >
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

function isNearBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_PX;
}

async function runFollow(
  service: string,
  tail: number,
  signal: AbortSignal,
  hooks: {
    onLine: (line: string) => void;
    onReady: () => void;
    onError: (msg: string) => void;
  },
): Promise<void> {
  try {
    const lines = await openServiceLogsFollow(service, tail, signal);
    if (signal.aborted) return;
    hooks.onReady();
    for await (const line of lines) {
      hooks.onLine(line);
    }
  } catch (err) {
    if (signal.aborted) return;
    hooks.onError(err instanceof Error ? err.message : "Failed to follow logs.");
  }
}
