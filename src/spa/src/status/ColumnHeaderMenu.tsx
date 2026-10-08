import { useEffect, useId, useRef, useState } from "react";
import {
  columnValueKind,
  defaultFilterOp,
  filterOpLabel,
  isActiveColumnFilter,
  operatorsFor,
  type ColumnFilter,
  type FilterOp,
  type SortKey,
} from "./statusColumnFilter";
import type { SortDir } from "./statusPanelView";
import "./ColumnHeaderMenu.css";
export function ColumnHeaderMenu(props: {
  label: string;
  columnKey: SortKey;
  sortKey: SortKey | null;
  sortDir: SortDir;
  filter: ColumnFilter | undefined;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  onSort: (key: SortKey, dir: SortDir) => void;
  onFilter: (key: SortKey, filter: ColumnFilter | null) => void;
}) {
  const menuId = useId();
  const rootRef = useRef<HTMLTableCellElement>(null);
  const sorted = props.sortKey === props.columnKey;
  const filtered = isActiveColumnFilter(props.filter);
  const ariaSort = !sorted
    ? "none"
    : props.sortDir === "asc"
      ? "ascending"
      : "descending";
  const sortMark = !sorted ? "↕" : props.sortDir === "asc" ? "↑" : "↓";

  useEffect(() => {
    if (!props.open) {
      return;
    }
    const onDoc = (event: MouseEvent) => {
      const node = rootRef.current;
      if (node && !node.contains(event.target as Node)) {
        props.onClose();
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        props.onClose();
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [props.open, props.onClose]);

  const btnClass = [
    "col-menu-btn",
    sorted ? "is-sorted" : "",
    filtered ? "is-filtered" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <th aria-sort={ariaSort} className="col-menu-th" ref={rootRef}>
      <button
        type="button"
        className={btnClass}
        aria-haspopup="dialog"
        aria-expanded={props.open}
        aria-controls={props.open ? menuId : undefined}
        onClick={props.onToggle}
      >
        <span>{props.label}</span>
        <span className="col-menu-marks" aria-hidden="true">
          <span className="sort-indicator">{sortMark}</span>
          {filtered ? <span className="filter-dot">●</span> : null}
        </span>
      </button>
      {props.open ? (
        <ColumnMenuPanel
          id={menuId}
          columnKey={props.columnKey}
          label={props.label}
          sorted={sorted}
          sortDir={props.sortDir}
          filter={props.filter}
          onSort={props.onSort}
          onFilter={props.onFilter}
          onClose={props.onClose}
        />
      ) : null}
    </th>
  );
}

function ColumnMenuPanel(props: {
  id: string;
  columnKey: SortKey;
  label: string;
  sorted: boolean;
  sortDir: SortDir;
  filter: ColumnFilter | undefined;
  onSort: (key: SortKey, dir: SortDir) => void;
  onFilter: (key: SortKey, filter: ColumnFilter | null) => void;
  onClose: () => void;
}) {
  const ops = operatorsFor(props.columnKey);
  const [op, setOp] = useState<FilterOp>(
    props.filter?.op ?? defaultFilterOp(props.columnKey),
  );
  const [value, setValue] = useState(props.filter?.value ?? "");
  const kind = columnValueKind(props.columnKey);
  const placeholder =
    kind === "numeric" ? "e.g. 50" : `Filter ${props.label.toLowerCase()}…`;

  const applyFilter = (nextOp: FilterOp, nextValue: string) => {
    setOp(nextOp);
    setValue(nextValue);
    if (!nextValue.trim()) {
      props.onFilter(props.columnKey, null);
      return;
    }
    props.onFilter(props.columnKey, { op: nextOp, value: nextValue });
  };

  return (
    <div
      id={props.id}
      className="col-menu"
      role="dialog"
      aria-label={`${props.label} column options`}
    >
      <div className="col-menu-section">
        <div className="col-menu-heading">Sort</div>
        <button
          type="button"
          className={
            props.sorted && props.sortDir === "asc"
              ? "col-menu-item is-active"
              : "col-menu-item"
          }
          onClick={() => {
            props.onSort(props.columnKey, "asc");
            props.onClose();
          }}
        >
          Ascending
        </button>
        <button
          type="button"
          className={
            props.sorted && props.sortDir === "desc"
              ? "col-menu-item is-active"
              : "col-menu-item"
          }
          onClick={() => {
            props.onSort(props.columnKey, "desc");
            props.onClose();
          }}
        >
          Descending
        </button>
      </div>
      <div className="col-menu-section">
        <div className="col-menu-heading">Filter</div>
        <label className="col-menu-field">
          Operator
          <select
            value={op}
            aria-label={`${props.label} filter operator`}
            onChange={(e) => applyFilter(e.target.value as FilterOp, value)}
          >
            {ops.map((item) => (
              <option key={item} value={item}>
                {filterOpLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label className="col-menu-field">
          Value
          <input
            type="text"
            value={value}
            placeholder={placeholder}
            aria-label={`${props.label} filter value`}
            onChange={(e) => applyFilter(op, e.target.value)}
          />
        </label>
        <button
          type="button"
          className="col-menu-clear"
          disabled={!value.trim()}
          onClick={() => applyFilter(op, "")}
        >
          Clear filter
        </button>
      </div>
    </div>
  );
}
