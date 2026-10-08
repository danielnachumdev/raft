import type { ReactNode } from "react";
import { trimFilterValues } from "./logFilter";
import type { ParsedLogLine } from "./logParse";
import "./LogLines.css";

/** Render parsed log lines with severity tint and optional search highlight. */
export function LogLines(props: {
  lines: ParsedLogLine[];
  highlightValues: string[];
  emptyLabel?: string;
}) {
  if (props.lines.length === 0) {
    return (
      <p className="logs-empty muted">
        {props.emptyLabel ?? "No matching lines."}
      </p>
    );
  }
  const onlyEmpty = props.lines.length === 1 && props.lines[0].raw === "";
  if (onlyEmpty) {
    return <p className="logs-empty muted">(no log output)</p>;
  }
  const needles = trimFilterValues(props.highlightValues);
  return (
    <div className="logs-lines" role="log" aria-live="polite">
      {props.lines.map((line, i) => (
        <LogLineRow key={i} line={line} needles={needles} />
      ))}
    </div>
  );
}

function LogLineRow(props: { line: ParsedLogLine; needles: string[] }) {
  const { line, needles } = props;
  const sev = line.severity === "unknown" ? "" : ` sev-${line.severity}`;
  return (
    <div className={`logs-line${sev}`}>
      {line.service ? (
        <span className="logs-svc">{highlight(line.service, needles)}</span>
      ) : null}
      {line.timestamp ? (
        <span className="logs-ts">{highlight(line.timestamp, needles)}</span>
      ) : null}
      {line.severity !== "unknown" ? (
        <span className={`logs-level logs-level-${line.severity}`}>
          {line.severity}
        </span>
      ) : null}
      <span className="logs-msg">
        {highlight(line.message || line.raw, needles)}
      </span>
    </div>
  );
}

function highlight(text: string, needles: string[]): ReactNode {
  if (!needles.length || !text) return text;
  const parts: ReactNode[] = [];
  let cursor = 0;
  let n = 0;
  while (cursor < text.length) {
    const hit = nextNeedle(text, needles, cursor);
    if (!hit) break;
    if (hit.index > cursor) parts.push(text.slice(cursor, hit.index));
    parts.push(
      <mark key={n++} className="logs-mark">
        {text.slice(hit.index, hit.index + hit.length)}
      </mark>,
    );
    cursor = hit.index + hit.length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts.length ? parts : text;
}

function nextNeedle(
  text: string,
  needles: string[],
  from: number,
): { index: number; length: number } | null {
  const lower = text.toLowerCase();
  let best: { index: number; length: number } | null = null;
  for (const needle of needles) {
    const idx = lower.indexOf(needle.toLowerCase(), from);
    if (idx === -1) continue;
    if (!best || idx < best.index || (idx === best.index && needle.length > best.length)) {
      best = { index: idx, length: needle.length };
    }
  }
  return best;
}
