import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { StatusRow } from "../shared/api";
import { servicePath } from "../shared/api";
import { ColumnHeaderMenu } from "./ColumnHeaderMenu";
import { ExternalUrlLinks } from "../shared/ExternalUrlLinks";
import { ServiceQuickActions } from "./ServiceQuickActions";
import { StatusPanelControls } from "./StatusPanelControls";
import { COLUMN_LABELS, type SortKey } from "./statusColumnFilter";
import { useStatusPanelView, type StatusTreeRow } from "./statusPanelView";
import {
  parseMemoryRatioPercent,
  parsePercent,
  statusTone,
  utilTone,
  type StatusTone,
  type UtilTone,
} from "./statusTone";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "name", label: COLUMN_LABELS.name },
  { key: "role", label: COLUMN_LABELS.role },
  { key: "group", label: COLUMN_LABELS.group },
  { key: "status", label: COLUMN_LABELS.status },
  { key: "cpu", label: COLUMN_LABELS.cpu },
  { key: "memory", label: COLUMN_LABELS.memory },
  { key: "started", label: COLUMN_LABELS.started },
  { key: "uptime", label: COLUMN_LABELS.uptime },
];

export function StatusTable(props: {
  rows: StatusRow[];
  empty: string;
  storageKey: string;
  onActionDone: () => void;
}) {
  const navigate = useNavigate();
  const view = useStatusPanelView(props.storageKey, props.rows);
  const [openKey, setOpenKey] = useState<SortKey | null>(null);
  const closeMenu = useCallback(() => setOpenKey(null), []);

  if (!props.rows.length) {
    return <p className="muted">{props.empty}</p>;
  }

  return (
    <div className="status-panel-body">
      <StatusPanelControls
        filtersActive={view.filtersActive}
        columnFilterEntries={view.columnFilterEntries}
        shown={view.visible.length}
        total={props.rows.length}
        onClear={view.clearFilters}
        onClearColumnFilter={(key) => view.setColumnFilter(key, null)}
      />
      {!view.visible.length ? (
        <p className="muted">No rows match the current filters.</p>
      ) : (
        <table className="status-table">
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <ColumnHeaderMenu
                  key={col.key}
                  label={col.label}
                  columnKey={col.key}
                  sortKey={view.prefs.sortKey}
                  sortDir={view.prefs.sortDir}
                  filter={view.prefs.columnFilters[col.key]}
                  open={openKey === col.key}
                  onToggle={() =>
                    setOpenKey((cur) => (cur === col.key ? null : col.key))
                  }
                  onClose={closeMenu}
                  onSort={view.setSort}
                  onFilter={view.setColumnFilter}
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

function StatusRowLink(props: {
  row: StatusTreeRow;
  onOpen: () => void;
  onActionDone: () => void;
}) {
  const { row, onOpen, onActionDone } = props;
  return (
    <tr
      className={row.treeDepth > 0 ? "status-row status-row--child" : "status-row"}
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

function cellContent(key: SortKey, row: StatusTreeRow) {
  if (key === "name") {
    return <NameCell row={row} />;
  }
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

function NameCell(props: { row: StatusTreeRow }) {
  const depth = props.row.treeDepth;
  return (
    <span
      className={
        depth > 0 ? "status-name-cell status-name-cell--tree" : "status-name-cell"
      }
      style={depth > 0 ? { ["--tree-depth" as string]: depth } : undefined}
    >
      {depth > 0 ? (
        <span className="status-tree-guide" aria-hidden="true" />
      ) : null}
      <span className="status-name-body">
        <span>{props.row.name}</span>
        <ExternalUrlLinks urls={props.row.external_urls ?? []} compact />
      </span>
    </span>
  );
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
