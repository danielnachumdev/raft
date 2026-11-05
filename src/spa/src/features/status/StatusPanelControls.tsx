import {
  COLUMN_LABELS,
  filterOpLabel,
  type ColumnFilter,
  type SortKey,
} from "./model/statusColumnFilter";
import "./StatusPanelControls.css";
export function StatusPanelControls(props: {
  filtersActive: boolean;
  columnFilterEntries: { key: SortKey; filter: ColumnFilter }[];
  shown: number;
  total: number;
  onClear: () => void;
  onClearColumnFilter: (key: SortKey) => void;
}) {
  if (!props.filtersActive) return null;
  return (
    <div className="status-controls-wrap">
      <div className="status-controls">
        <div className="status-controls-meta">
          <span className="muted status-count" aria-live="polite">
            Showing {props.shown} of {props.total}
          </span>
          <button
            type="button"
            className="status-clear"
            onClick={props.onClear}
          >
            Clear filters
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
