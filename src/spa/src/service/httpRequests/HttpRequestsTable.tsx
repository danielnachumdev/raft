import { useState } from "react";
import type { HttpRequestRow } from "../../shared/api";
import {
  HTTP_REQUEST_COLUMNS,
  tableMinWidth,
  type HttpRequestColumnKey,
} from "./columnResize";
import { InspectionFirewallActions } from "./InspectionFirewallActions";
import {
  formatLatencyMs,
  formatRequestTime,
  formatRequestTimeFull,
  statusToneForCode,
} from "./statusClass";
import { useColumnResize } from "./useColumnResize";

/** Scrollable request table with resizable columns and expandable rows. */
export function HttpRequestsTable(props: {
  rows: HttpRequestRow[];
  /** App name for firewall service prefill (Host-routed). */
  appName: string | null;
  /** Distinguish true empty history from scaled/stopped idle states. */
  emptyLabel?: string;
}) {
  const resize = useColumnResize();
  const [expanded, setExpanded] = useState<string | null>(null);

  if (props.rows.length === 0) {
    return (
      <p className="http-requests-empty">
        {props.emptyLabel ?? "No recent HTTP requests for this service."}
      </p>
    );
  }

  const widthPx = tableMinWidth(resize.widths);
  return (
    <div className="http-requests-scroll">
      <table
        className="http-requests-table"
        style={{ width: widthPx, minWidth: widthPx }}
      >
        <colgroup>
          {HTTP_REQUEST_COLUMNS.map((col) => (
            <col key={col.key} style={{ width: resize.widths[col.key] }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {HTTP_REQUEST_COLUMNS.map((col) => (
              <ResizableTh
                key={col.key}
                label={col.label}
                columnKey={col.key}
                onPointerDown={resize.onResizePointerDown}
                onPointerMove={resize.onResizePointerMove}
                onPointerUp={resize.onResizePointerUp}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row, idx) => {
            const rowKey = `${row.ts}-${idx}`;
            return (
              <HttpRequestRowView
                key={rowKey}
                row={row}
                rowKey={rowKey}
                appName={props.appName}
                expanded={expanded === rowKey}
                onToggle={() =>
                  setExpanded((cur) => (cur === rowKey ? null : rowKey))
                }
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ResizableTh(props: {
  label: string;
  columnKey: HttpRequestColumnKey;
  onPointerDown: (key: HttpRequestColumnKey, clientX: number) => void;
  onPointerMove: (clientX: number) => void;
  onPointerUp: () => void;
}) {
  return (
    <th scope="col">
      <span className="http-requests-th-label">{props.label}</span>
      <span
        className="http-requests-col-resizer"
        role="separator"
        aria-orientation="vertical"
        aria-label={`Resize ${props.label} column`}
        onPointerDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          (e.target as HTMLElement).setPointerCapture(e.pointerId);
          props.onPointerDown(props.columnKey, e.clientX);
        }}
        onPointerMove={(e) => {
          if (!(e.target as HTMLElement).hasPointerCapture(e.pointerId)) return;
          props.onPointerMove(e.clientX);
        }}
        onPointerUp={(e) => {
          if ((e.target as HTMLElement).hasPointerCapture(e.pointerId)) {
            (e.target as HTMLElement).releasePointerCapture(e.pointerId);
          }
          props.onPointerUp();
        }}
      />
    </th>
  );
}

function HttpRequestRowView(props: {
  row: HttpRequestRow;
  rowKey: string;
  appName: string | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { row } = props;
  const tone = statusToneForCode(row.status);
  const ua = row.user_agent ?? "—";
  const path = row.path ?? "—";
  return (
    <tr
      className={props.expanded ? "is-expanded" : undefined}
      onClick={props.onToggle}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          props.onToggle();
        }
      }}
      tabIndex={0}
      aria-expanded={props.expanded}
      title={
        props.expanded
          ? "Click to collapse request details"
          : "Click to expand full request details"
      }
    >
      <td className="http-requests-time" title={formatRequestTimeFull(row.ts)}>
        {formatRequestTime(row.ts)}
      </td>
      <td>
        <code>{row.method ?? "—"}</code>
      </td>
      <td className="http-requests-path">
        <code title={path}>{path}</code>
      </td>
      <td>
        <span className={`http-requests-status tone-${tone}`}>{row.status}</span>
      </td>
      <td>{formatLatencyMs(row.duration_ms)}</td>
      <td>
        <code>{row.client_ip ?? "—"}</code>
      </td>
      <td>
        <code>{row.host}</code>
      </td>
      <td className="http-requests-ua" title={ua}>
        {ua}
      </td>
      <td
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        {row.client_ip ? (
          <InspectionFirewallActions
            clientIp={row.client_ip}
            appName={props.appName}
          />
        ) : (
          <span className="muted">—</span>
        )}
      </td>
    </tr>
  );
}
