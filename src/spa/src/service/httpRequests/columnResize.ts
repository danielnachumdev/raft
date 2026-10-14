/** Column keys and pure width helpers for the HTTP requests table. */

export const HTTP_REQUEST_COLUMNS = [
  { key: "time", label: "Time", defaultWidth: 148 },
  { key: "method", label: "Method", defaultWidth: 72 },
  { key: "path", label: "Path", defaultWidth: 180 },
  { key: "status", label: "Status", defaultWidth: 68 },
  { key: "latency", label: "Latency", defaultWidth: 76 },
  { key: "client", label: "Client", defaultWidth: 112 },
  { key: "host", label: "Host", defaultWidth: 140 },
  { key: "ua", label: "User-Agent", defaultWidth: 240 },
  { key: "firewall", label: "Firewall", defaultWidth: 148 },
] as const;

export type HttpRequestColumnKey = (typeof HTTP_REQUEST_COLUMNS)[number]["key"];

export type ColumnWidths = Record<HttpRequestColumnKey, number>;

export const MIN_COLUMN_WIDTH = 48;
export const MAX_COLUMN_WIDTH = 720;

export function defaultColumnWidths(): ColumnWidths {
  const widths = {} as ColumnWidths;
  for (const col of HTTP_REQUEST_COLUMNS) {
    widths[col.key] = col.defaultWidth;
  }
  return widths;
}

export function clampColumnWidth(px: number): number {
  if (!Number.isFinite(px)) return MIN_COLUMN_WIDTH;
  return Math.min(MAX_COLUMN_WIDTH, Math.max(MIN_COLUMN_WIDTH, Math.round(px)));
}

export function applyColumnResize(
  widths: ColumnWidths,
  key: HttpRequestColumnKey,
  startWidth: number,
  deltaX: number,
): ColumnWidths {
  return { ...widths, [key]: clampColumnWidth(startWidth + deltaX) };
}

export function tableMinWidth(widths: ColumnWidths): number {
  return HTTP_REQUEST_COLUMNS.reduce((sum, col) => sum + widths[col.key], 0);
}
