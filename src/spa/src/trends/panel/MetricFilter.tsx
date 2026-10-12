import type { RuntimeMetricId } from "../runtimeMetrics";
import {
  isMetricTypeBlocked,
  metricFilterSections,
  THIRD_TYPE_BLOCK_REASON,
} from "./metricSelection";

export function MetricFilter(props: {
  activeIds: RuntimeMetricId[];
  busy: boolean;
  onToggle: (id: RuntimeMetricId) => void;
  onClearAll: () => void;
}) {
  const noneSelected = props.activeIds.length === 0;
  return (
    <div className="trends-services-block trends-metrics-block">
      <div className="trends-services-head">
        <span className="trends-services-title">Metrics</span>
        <div className="trends-services-actions">
          <button
            type="button"
            className="trends-clear-all"
            onClick={props.onClearAll}
            disabled={props.busy || noneSelected}
          >
            Clear all
          </button>
        </div>
      </div>
      <div className="trends-services-list" role="group" aria-label="Metrics">
        {metricFilterSections().map((section) => (
          <div key={section.plane} className="trends-metric-plane-block">
            <p className="trends-metric-plane">{section.planeLabel}</p>
            {section.types.map(({ type, metrics }) => (
              <div key={type.id} className="trends-metric-type-block">
                <p className="trends-metric-type">{type.label}</p>
                {metrics.map((m) => {
                  const typeBlocked = isMetricTypeBlocked(
                    props.activeIds,
                    m.id,
                  );
                  return (
                    <MetricChip
                      key={m.id}
                      id={m.id}
                      label={m.label}
                      checked={props.activeIds.includes(m.id)}
                      busy={props.busy}
                      typeBlocked={typeBlocked}
                      onToggle={props.onToggle}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricChip(props: {
  id: RuntimeMetricId;
  label: string;
  checked: boolean;
  busy: boolean;
  typeBlocked: boolean;
  onToggle: (id: RuntimeMetricId) => void;
}) {
  const blocked = props.typeBlocked && !props.checked;
  const disabled = props.busy || blocked;
  const reason = blocked ? THIRD_TYPE_BLOCK_REASON : undefined;
  return (
    <label
      className={
        blocked ? "trends-chip trends-chip-type-blocked" : "trends-chip"
      }
      title={reason}
    >
      <input
        type="checkbox"
        checked={props.checked}
        onChange={() => props.onToggle(props.id)}
        disabled={disabled}
        aria-disabled={disabled || undefined}
        aria-description={reason}
      />
      <span className="trends-chip-label">{props.label}</span>
    </label>
  );
}
