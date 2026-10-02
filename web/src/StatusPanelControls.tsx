import {
  COLUMN_LABELS,
  filterOpLabel,
  type ColumnFilter,
  type SortKey,
} from "./statusColumnFilter";
import type { StatusPanelPrefs } from "./statusPanelView";

export function StatusPanelControls(props: {
  prefs: StatusPanelPrefs;
  statusOptions: string[];
  filtersActive: boolean;
  columnFilterEntries: { key: SortKey; filter: ColumnFilter }[];
  shown: number;
  total: number;
  onQuery: (value: string) => void;
  onStatus: (value: string) => void;
  onClear: () => void;
  onClearColumnFilter: (key: SortKey) => void;
}) {
  const { prefs } = props;
  return (
    <div className="status-controls-wrap">
      <div className="status-controls" role="search">
        <label className="status-field">
          Search
          <input
            type="search"
            className="status-search"
            value={prefs.query}
            onChange={(e) => props.onQuery(e.target.value)}
            placeholder="Name, service, group…"
            aria-label="Filter by name, service, or group"
          />
        </label>
        <label className="status-field">
          Status
          <select
            value={prefs.status}
            onChange={(e) => props.onStatus(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="">All</option>
            {props.statusOptions.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </label>
        <div className="status-controls-meta">
          <span className="muted status-count" aria-live="polite">
            {props.shown === props.total
              ? `${props.total}`
              : `${props.shown} / ${props.total}`}
          </span>
          <button
            type="button"
            className="status-clear"
            onClick={props.onClear}
            disabled={!props.filtersActive}
          >
            Clear
          </button>
        </div>
      </div>
      {props.columnFilterEntries.length ? (
        <div className="column-filter-chips" aria-label="Active column filters">
          {props.columnFilterEntries.map(({ key, filter }) => (
            <button
              key={key}
              type="button"
              className="column-filter-chip"
              onClick={() => props.onClearColumnFilter(key)}
              title="Clear column filter"
            >
              <span>
                {COLUMN_LABELS[key]} {filterOpLabel(filter.op)} “{filter.value}”
              </span>
              <span aria-hidden="true">×</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
