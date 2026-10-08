import type { ReactNode } from "react";
import type { ParsedLogLine } from "./logParse";
import "./LogLines.css";
/** Render parsed log lines with severity tint and optional search highlight. */
export function LogLines(props: {
  lines: ParsedLogLine[];
  query: string;
  emptyLabel?: string;
}) {
  if (props.lines.length === 0) {
    return (
      <p className="logs-empty muted">
        {props.emptyLabel ?? "No matching lines."}
      </p>
    );
  }
  const onlyEmpty =
    props.lines.length === 1 && props.lines[0].raw === "";
  if (onlyEmpty) {
    return <p className="logs-empty muted">(no log output)</p>;
  }
  return (
    <div className="logs-lines" role="log" aria-live="polite">
      {props.lines.map((line, i) => (
        <LogLineRow key={i} line={line} query={props.query} />
      ))}
    </div>
  );
}

function LogLineRow(props: { line: ParsedLogLine; query: string }) {
  const { line, query } = props;
  const sev = line.severity === "unknown" ? "" : ` sev-${line.severity}`;
  return (
    <div className={`logs-line${sev}`}>
      {line.service ? (
        <span className="logs-svc">{highlight(line.service, query)}</span>
      ) : null}
      {line.timestamp ? (
        <span className="logs-ts">{highlight(line.timestamp, query)}</span>
      ) : null}
      {line.severity !== "unknown" ? (
        <span className={`logs-level logs-level-${line.severity}`}>
          {line.severity}
        </span>
      ) : null}
      <span className="logs-msg">
        {highlight(line.message || line.raw, query)}
      </span>
    </div>
  );
}

function highlight(text: string, query: string): ReactNode {
  const q = query.trim();
  if (!q || !text) return text;
  const lower = text.toLowerCase();
  const needle = q.toLowerCase();
  const parts: ReactNode[] = [];
  let start = 0;
  let idx = lower.indexOf(needle, start);
  let n = 0;
  while (idx !== -1) {
    if (idx > start) parts.push(text.slice(start, idx));
    parts.push(
      <mark key={n++} className="logs-mark">
        {text.slice(idx, idx + q.length)}
      </mark>,
    );
    start = idx + q.length;
    idx = lower.indexOf(needle, start);
  }
  if (start < text.length) parts.push(text.slice(start));
  return parts.length ? parts : text;
}
