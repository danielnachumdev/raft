import type { MetricsBounds } from "../shared/api";
import { RUNTIME_WINDOWS } from "./runtimeMetrics";
import {
  applyAbsoluteTimes,
  applyCustomDuration,
  availableFromMs,
  maxWindowSec,
  presetSelectValue,
  selectRangeKind,
  toDatetimeLocal,
  type DurationUnit,
  type TrendsRangeState,
} from "./trendsRange";
import "./TrendsRangeControls.css";
export function TrendsRangeControls(props: {
  range: TrendsRangeState;
  bounds: MetricsBounds | null;
  clampMessage: string | null;
  busy: boolean;
  onChange: (next: TrendsRangeState) => void;
}) {
  const maxW = maxWindowSec(props.bounds);
  const minLocal = toDatetimeLocal(availableFromMs(props.bounds));
  const maxLocal = toDatetimeLocal(Date.now());
  return (
    <div className="trends-range">
      <label className="trends-field">
        <span>Range</span>
        <select
          value={presetSelectValue(props.range)}
          onChange={(e) =>
            props.onChange(
              selectRangeKind(props.range, e.target.value, props.bounds),
            )
          }
          aria-label="Time range"
          disabled={props.busy}
        >
          {RUNTIME_WINDOWS.map((w) => (
            <option key={w.seconds} value={w.seconds} disabled={w.seconds > maxW}>
              {w.label}
            </option>
          ))}
          <option value="custom">Custom…</option>
          <option value="absolute">Specific time…</option>
        </select>
      </label>
      {props.range.mode === "custom" ? <CustomDurationFields {...props} /> : null}
      {props.range.mode === "absolute" ? (
        <AbsoluteTimeFields {...props} minLocal={minLocal} maxLocal={maxLocal} />
      ) : null}
      <p className="muted trends-range-hint">{retentionHint(props.bounds)}</p>
      {props.clampMessage ? (
        <p className="trends-range-limit" role="status">
          {props.clampMessage}
        </p>
      ) : null}
    </div>
  );
}

function CustomDurationFields(props: {
  range: TrendsRangeState;
  busy: boolean;
  bounds: MetricsBounds | null;
  onChange: (next: TrendsRangeState) => void;
}) {
  const apply = (amount: number, unit: DurationUnit) =>
    props.onChange(applyCustomDuration(props.range, amount, unit, props.bounds));
  return (
    <div className="trends-range-custom">
      <label className="trends-field">
        <span>Duration</span>
        <input
          type="number"
          min={1}
          step="any"
          value={props.range.customAmount}
          onChange={(e) => apply(Number(e.target.value), props.range.customUnit)}
          aria-label="Custom duration"
          disabled={props.busy}
        />
      </label>
      <label className="trends-field">
        <span>Unit</span>
        <select
          value={props.range.customUnit}
          onChange={(e) =>
            apply(props.range.customAmount, e.target.value as DurationUnit)
          }
          aria-label="Duration unit"
          disabled={props.busy}
        >
          <option value="minutes">Minutes</option>
          <option value="hours">Hours</option>
          <option value="days">Days</option>
        </select>
      </label>
    </div>
  );
}

function AbsoluteTimeFields(props: {
  range: TrendsRangeState;
  busy: boolean;
  bounds: MetricsBounds | null;
  minLocal: string;
  maxLocal: string;
  onChange: (next: TrendsRangeState) => void;
}) {
  const set = (startLocal: string, endLocal: string) =>
    props.onChange(
      applyAbsoluteTimes(props.range, startLocal, endLocal, props.bounds),
    );
  return (
    <div className="trends-range-absolute">
      <label className="trends-field">
        <span>From</span>
        <input
          type="datetime-local"
          value={props.range.startLocal}
          min={props.minLocal}
          max={props.maxLocal}
          onChange={(e) => set(e.target.value, props.range.endLocal)}
          aria-label="Range start"
          disabled={props.busy}
        />
      </label>
      <label className="trends-field">
        <span>To</span>
        <input
          type="datetime-local"
          value={props.range.endLocal}
          min={props.minLocal}
          max={props.maxLocal}
          onChange={(e) => set(props.range.startLocal, e.target.value)}
          aria-label="Range end"
          disabled={props.busy}
        />
      </label>
    </div>
  );
}

function retentionHint(bounds: MetricsBounds | null): string {
  if (!bounds) return "History follows metrics retention in settings.";
  const from = new Date(bounds.available_from);
  const when = Number.isNaN(from.getTime())
    ? `${bounds.retention_max_age_days} days`
    : from.toLocaleString();
  return `Available from ${when} (${bounds.retention_max_age_days}-day retention).`;
}
