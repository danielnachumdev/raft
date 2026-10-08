import { useCallback, useEffect, useState } from "react";
import { DownloadMenu } from "../export/DownloadMenu";
import { logsDownloadUrl } from "../export/urls";
import {
  DEFAULT_LOG_TAIL,
  fetchServiceLogs,
  openServiceLogsFollow,
} from "../shared/api";
import { LogViewer } from "./LogViewer";
import "./ServiceLogs.css";

const TAIL_CHOICES = [50, 100, 200, 500] as const;

/** Service log stream adapter — follow/snapshot feed into shared LogViewer. */
export function ServiceLogs(props: { service: string }) {
  const [tail, setTail] = useState<number>(DEFAULT_LOG_TAIL);
  const [follow, setFollow] = useState(true);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [epoch, setEpoch] = useState(0);
  const resubscribe = useCallback(() => setEpoch((n) => n + 1), []);

  useSnapshot(props.service, tail, follow, epoch, setText, setBusy, setError);
  useFollow(props.service, tail, follow, epoch, setText, setBusy, setError);

  return (
    <LogViewer
      title="Logs"
      overlayTitle={`Logs — ${props.service}`}
      text={text}
      busy={busy}
      error={error}
      connectingLabel={follow ? "Connecting…" : "Loading logs…"}
      controls={
        <ServiceLogControls
          follow={follow}
          onFollowChange={setFollow}
          tail={tail}
          onTailChange={setTail}
          busy={busy}
          textEmpty={text === ""}
          error={error}
          service={props.service}
          onRefresh={resubscribe}
        />
      }
    />
  );
}

function ServiceLogControls(props: {
  follow: boolean;
  onFollowChange: (v: boolean) => void;
  tail: number;
  onTailChange: (v: number) => void;
  busy: boolean;
  textEmpty: boolean;
  error: string | null;
  service: string;
  onRefresh: () => void;
}) {
  const loading = props.busy && props.textEmpty;
  return (
    <>
      <label className="logs-follow">
        <input
          type="checkbox"
          checked={props.follow}
          onChange={(e) => props.onFollowChange(e.target.checked)}
        />
        Follow
      </label>
      <label className="logs-tail">
        Tail
        <select
          value={props.tail}
          disabled={loading}
          onChange={(e) => props.onTailChange(Number(e.target.value))}
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
        className={`refresh${props.busy ? " is-loading" : ""}`}
        disabled={loading}
        aria-busy={props.busy}
        onClick={props.onRefresh}
      >
        {props.busy ? (
          <span className="spinner refresh-spinner" aria-hidden="true" />
        ) : null}
        Refresh
      </button>
      <DownloadMenu
        kind="logs"
        hrefFor={(formatId) =>
          logsDownloadUrl(props.service, formatId, props.tail)
        }
        disabled={Boolean(props.error)}
      />
    </>
  );
}

function useSnapshot(
  service: string,
  tail: number,
  follow: boolean,
  epoch: number,
  setText: (t: string) => void,
  setBusy: (b: boolean) => void,
  setError: (e: string | null) => void,
): void {
  useEffect(() => {
    if (follow) return;
    let cancelled = false;
    setBusy(true);
    setError(null);
    void fetchServiceLogs(service, tail)
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
  }, [follow, service, tail, epoch, setText, setBusy, setError]);
}

function useFollow(
  service: string,
  tail: number,
  follow: boolean,
  epoch: number,
  setText: (updater: string | ((prev: string) => string)) => void,
  setBusy: (b: boolean) => void,
  setError: (e: string | null) => void,
): void {
  useEffect(() => {
    if (!follow) return;
    const ac = new AbortController();
    setBusy(true);
    setError(null);
    setText("");
    void runFollow(service, tail, ac.signal, {
      onLine: (line) => setText((prev) => (prev ? `${prev}\n${line}` : line)),
      onReady: () => setBusy(false),
      onError: (msg) => {
        setError(msg);
        setBusy(false);
      },
    });
    return () => ac.abort();
  }, [follow, service, tail, epoch, setText, setBusy, setError]);
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
