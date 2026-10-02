import { useNavigate } from "react-router-dom";
import type { StatusRow } from "./api";
import { servicePath } from "./api";
import { ServiceQuickActions } from "./ServiceQuickActions";
import { StatusPanelControls } from "./StatusPanelControls";
import {
  type SortDir,
  type SortKey,
  useStatusPanelView,
} from "./statusPanelView";
import {
  parseMemoryRatioPercent,
  parsePercent,
  statusTone,
  utilTone,
  type StatusTone,
  type UtilTone,
} from "./statusTone";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "role", label: "Role" },
  { key: "group", label: "Group" },
  { key: "status", label: "Status" },
  { key: "cpu", label: "CPU" },
  { key: "memory", label: "Memory" },
  { key: "started", label: "Started" },
  { key: "uptime", label: "Uptime" },
];

export function StatusTable(props: {
  rows: StatusRow[];
  empty: string;
  storageKey: string;
  onActionDone: () => void;
}) {
  const navigate = useNavigate();
  const view = useStatusPanelView(props.storageKey, props.rows);

  if (!props.rows.length) {
    return <p className="muted">{props.empty}</p>;
  }

  const tableClass =
    view.prefs.density === "compact"
      ? "status-table status-table-compact"
      : "status-table";

  return (
    <div className="status-panel-body">
      <StatusPanelControls
        prefs={view.prefs}
        statusOptions={view.statusOptions}
        filtersActive={view.filtersActive}
        shown={view.visible.length}
        total={props.rows.length}
        onQuery={view.setQuery}
        onStatus={view.setStatus}
        onDensity={view.setDensity}
        onClear={view.clearFilters}
      />
      {!view.visible.length ? (
        <p className="muted">No rows match the current filters.</p>
      ) : (
        <table className={tableClass}>
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <SortHeader
                  key={col.key}
                  label={col.label}
                  columnKey={col.key}
                  activeKey={view.prefs.sortKey}
                  dir={view.prefs.sortDir}
                  onSort={view.toggleSort}
                />
              ))}
              <th className="actions-col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {view.visible.map((row) => (
              <StatusRowLink
                key={`${row.role}-${row.service}`}
                row={row}
                onOpen={() => navigate(servicePath(row.service))}
                onActionDone={props.onActionDone}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SortHeader(props: {
  label: string;
  columnKey: SortKey;
  activeKey: SortKey | null;
  dir: SortDir;
  onSort: (key: SortKey) => void;
}) {
  const active = props.activeKey === props.columnKey;
  const ariaSort = !active
    ? "none"
    : props.dir === "asc"
      ? "ascending"
      : "descending";
  const indicator = !active ? "↕" : props.dir === "asc" ? "↑" : "↓";
  return (
    <th aria-sort={ariaSort}>
      <button
        type="button"
        className={active ? "sort-btn is-active" : "sort-btn"}
        onClick={() => props.onSort(props.columnKey)}
      >
        {props.label}
        <span className="sort-indicator" aria-hidden="true">
          {indicator}
        </span>
      </button>
    </th>
  );
}

function StatusRowLink(props: {
  row: StatusRow;
  onOpen: () => void;
  onActionDone: () => void;
}) {
  const { row, onOpen, onActionDone } = props;
  return (
    <tr
      className="status-row"
      tabIndex={0}
      role="link"
      aria-label={`Open ${row.name}`}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {COLUMNS.map((col) => (
        <td key={col.key}>{cellContent(col.key, row)}</td>
      ))}
      <td className="actions-col">
        <ServiceQuickActions
          service={row.service}
          name={row.name}
          onDone={onActionDone}
        />
      </td>
    </tr>
  );
}

function cellContent(key: SortKey, row: StatusRow) {
  const value = row[key];
  if (key === "status") {
    return <StatusBadge value={value} />;
  }
  if (key === "cpu") {
    return <UtilValue value={value} tone={utilTone(parsePercent(value))} />;
  }
  if (key === "memory") {
    return (
      <UtilValue value={value} tone={utilTone(parseMemoryRatioPercent(value))} />
    );
  }
  return value;
}

function StatusBadge(props: { value: string }) {
  const tone: StatusTone = statusTone(props.value);
  return (
    <span className={`status-badge tone-${tone}`} title={`Status: ${props.value}`}>
      {props.value}
    </span>
  );
}

function UtilValue(props: { value: string; tone: UtilTone }) {
  const className = props.tone ? `util-value util-${props.tone}` : "util-value";
  return <span className={className}>{props.value}</span>;
}
