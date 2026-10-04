/** Light parsing for docker compose / raft logs lines (client-side v1). */

export type LogSeverity = "error" | "warn" | "info" | "debug" | "unknown";

export type ParsedLogLine = {
  raw: string;
  service: string | null;
  timestamp: string | null;
  severity: LogSeverity;
  message: string;
};

const COMPOSE_PREFIX = /^([A-Za-z0-9][A-Za-z0-9_.-]*)\s+\|\s(.*)$/;
const ISO_TS =
  /^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+(.*)$/;
const PY_TS =
  /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)\s+(.*)$/;
const LEVEL_WORD =
  /\b(ERROR|ERR|FATAL|CRITICAL|WARN(?:ING)?|INFO|DEBUG|TRACE)\b/i;

/** Split raw log blob into parsed lines (empty blob → one empty placeholder). */
export function parseLogText(text: string): ParsedLogLine[] {
  if (!text) return [parseLogLine("")];
  return text.split("\n").map(parseLogLine);
}

/** Parse one compose/raft-style log line for display cues. */
export function parseLogLine(raw: string): ParsedLogLine {
  const compose = COMPOSE_PREFIX.exec(raw);
  const service = compose ? compose[1] : null;
  let rest = compose ? compose[2] : raw;
  let timestamp: string | null = null;
  const iso = ISO_TS.exec(rest) || PY_TS.exec(rest);
  if (iso) {
    timestamp = iso[1];
    rest = iso[2];
  }
  return {
    raw,
    service,
    timestamp,
    severity: detectSeverity(raw),
    message: rest,
  };
}

/** Case-insensitive substring filter over the original line text. */
export function filterLogLines(
  lines: ParsedLogLine[],
  query: string,
): ParsedLogLine[] {
  const q = query.trim().toLowerCase();
  if (!q) return lines;
  return lines.filter((line) => line.raw.toLowerCase().includes(q));
}

function detectSeverity(raw: string): LogSeverity {
  const m = LEVEL_WORD.exec(raw);
  if (!m) return "unknown";
  const word = m[1].toUpperCase();
  if (word === "ERROR" || word === "ERR" || word === "FATAL" || word === "CRITICAL") {
    return "error";
  }
  if (word === "WARN" || word === "WARNING") return "warn";
  if (word === "INFO") return "info";
  if (word === "DEBUG" || word === "TRACE") return "debug";
  return "unknown";
}
