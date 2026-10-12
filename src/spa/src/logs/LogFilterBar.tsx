import {
  isLogFilterActive,
  LOG_FILTER_OPS,
  logFilterOpLabel,
  type LogFilter,
  type LogFilterOp,
} from "./model/logFilter";
import "./LogFilterBar.css";

/** Operator selector + multi-value string boxes for client-side log filtering. */
export function LogFilterBar(props: {
  filter: LogFilter;
  matchCount: number;
  totalCount: number;
  onChange: (next: LogFilter) => void;
}) {
  const { filter, onChange } = props;

  return (
    <div className="logs-filter" role="group" aria-label="Log filter">
      <label className="logs-filter-op">
        <span className="logs-filter-label">Filter</span>
        <select
          value={filter.op}
          aria-label="Filter operator"
          onChange={(e) =>
            onChange({ ...filter, op: e.target.value as LogFilterOp })
          }
        >
          {LOG_FILTER_OPS.map((op) => (
            <option key={op} value={op}>
              {logFilterOpLabel(op)}
            </option>
          ))}
        </select>
      </label>
      <div className="logs-filter-values">
        {filter.values.map((value, index) => (
          <FilterValueRow
            key={index}
            index={index}
            value={value}
            canRemove={filter.values.length > 1}
            onChange={(next) => onChange(replaceValue(filter, index, next))}
            onRemove={() => onChange(removeValue(filter, index))}
          />
        ))}
        <button
          type="button"
          className="logs-filter-add"
          onClick={() => onChange({ ...filter, values: [...filter.values, ""] })}
        >
          Add value
        </button>
      </div>
      {isLogFilterActive(filter) ? (
        <span className="logs-match-count muted">
          {props.matchCount}/{props.totalCount}
        </span>
      ) : null}
    </div>
  );
}

function FilterValueRow(props: {
  index: number;
  value: string;
  canRemove: boolean;
  onChange: (value: string) => void;
  onRemove: () => void;
}) {
  return (
    <div className="logs-filter-value-row">
      <input
        type="text"
        value={props.value}
        placeholder={`Value ${props.index + 1}`}
        aria-label={`Filter value ${props.index + 1}`}
        onChange={(e) => props.onChange(e.target.value)}
        autoComplete="off"
        spellCheck={false}
      />
      {props.canRemove ? (
        <button
          type="button"
          className="logs-filter-remove"
          aria-label={`Remove filter value ${props.index + 1}`}
          onClick={props.onRemove}
        >
          Remove
        </button>
      ) : null}
    </div>
  );
}

function replaceValue(filter: LogFilter, index: number, value: string): LogFilter {
  const values = filter.values.slice();
  values[index] = value;
  return { ...filter, values };
}

function removeValue(filter: LogFilter, index: number): LogFilter {
  if (filter.values.length <= 1) return filter;
  return {
    ...filter,
    values: filter.values.filter((_, i) => i !== index),
  };
}
