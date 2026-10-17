import type { MetricsAvailable } from "../../../shared/api";
import { IdFilter } from "../../panel/IdFilter";
import { MetricFilter } from "../../panel/MetricFilter";
import { toggleMetricId } from "../../panel/metricSelection";
import { toggleId } from "../../panel/trendsPoll";
import { groupOptions, type SeriesViewMode } from "../../panel/trendsView";
import {
  GRAPH_PRESETS,
  graphTitle,
  pickerIdsFor,
  reconcileSelection,
  VIEW_MODE_LABELS,
  type GraphPreset,
  type GraphSize,
  type TrendsGraphDraft,
} from "../model/index.ts";
import "../../panel/TrendsFilters.css";

type Props = {
  draft: TrendsGraphDraft;
  available: MetricsAvailable[];
  showPresets: boolean;
  /** Service page: hide view / series pickers (graphs stay on that service). */
  pinnedService?: string;
  onChange: (next: TrendsGraphDraft) => void;
};

/** Graph fields: preset shortcuts, title, width, view, metrics, series picker. */
export function GraphEditorForm(props: Props) {
  const { draft, onChange } = props;
  const pinned = Boolean(props.pinnedService);
  const set = (patch: Partial<TrendsGraphDraft>) => onChange({ ...draft, ...patch });
  return (
    <div className="graph-editor-form">
      {props.showPresets ? (
        <PresetRow
          activeKey={draft.metricIds.join(",")}
          onPick={(p) => set({ title: p.title, metricIds: [...p.metricIds] })}
        />
      ) : null}
      <label className="trends-field">
        <span>Title</span>
        <input
          type="text"
          value={draft.title}
          placeholder={graphTitle({ ...draft, title: "" })}
          onChange={(e) => set({ title: e.target.value })}
          aria-label="Graph title"
        />
      </label>
      <div className="graph-editor-row">
        {pinned ? null : (
          <ViewModeField
            value={draft.viewMode}
            onChange={(viewMode) => set({ viewMode, selected: null })}
          />
        )}
        <SizeField value={draft.size} onChange={(size) => set({ size })} />
      </div>
      {pinned && props.pinnedService ? (
        <p className="muted graph-editor-pinned" role="note">
          Showing metrics for <strong>{props.pinnedService}</strong> only.
        </p>
      ) : null}
      <MetricFilter
        activeIds={draft.metricIds}
        busy={false}
        onToggle={(id) => set({ metricIds: toggleMetricId(draft.metricIds, id) })}
        onClearAll={() => set({ metricIds: [] })}
      />
      {pinned ? null : <SeriesField {...props} />}
    </div>
  );
}

function PresetRow(props: { activeKey: string; onPick: (p: GraphPreset) => void }) {
  return (
    <div className="graph-editor-presets" role="group" aria-label="Start from a preset">
      <span className="trends-services-title">Start from</span>
      <div className="graph-editor-preset-list">
        {GRAPH_PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            className="graph-editor-preset"
            title={p.hint}
            aria-pressed={p.metricIds.join(",") === props.activeKey}
            onClick={() => props.onPick(p)}
          >
            {p.title}
          </button>
        ))}
      </div>
    </div>
  );
}

function ViewModeField(props: { value: SeriesViewMode; onChange: (m: SeriesViewMode) => void }) {
  return (
    <label className="trends-field">
      <span>View</span>
      <select
        value={props.value}
        onChange={(e) => props.onChange(e.target.value as SeriesViewMode)}
        aria-label="Series view"
      >
        {(Object.keys(VIEW_MODE_LABELS) as SeriesViewMode[]).map((m) => (
          <option key={m} value={m}>
            {VIEW_MODE_LABELS[m]}
          </option>
        ))}
      </select>
    </label>
  );
}

function SizeField(props: { value: GraphSize; onChange: (s: GraphSize) => void }) {
  return (
    <div className="trends-field">
      <span>Width</span>
      <div className="graph-editor-segment" role="radiogroup" aria-label="Graph width">
        {(["half", "full"] as GraphSize[]).map((s) => (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={props.value === s}
            className={props.value === s ? "is-on" : ""}
            onClick={() => props.onChange(s)}
          >
            {s === "half" ? "Half" : "Full"}
          </button>
        ))}
      </div>
    </div>
  );
}

function SeriesField(props: Props) {
  const { draft } = props;
  const groupMode = draft.viewMode === "per_group" || draft.viewMode === "avg_group";
  const pickerIds = pickerIdsFor(groupMode, props.available);
  const activeIds = reconcileSelection(draft.selected, pickerIds).selected ?? pickerIds;
  const items = groupMode
    ? groupOptions(props.available)
    : props.available.map((a) => ({ id: a.id, label: a.label }));
  const noun = groupMode ? "groups" : "services";
  return (
    <IdFilter
      title={groupMode ? "Groups" : "Services"}
      searchLabel={`Search ${noun}`}
      searchPlaceholder={`Search ${noun}`}
      emptyLabel={`No matching ${noun}`}
      items={items}
      activeIds={activeIds}
      showingAll={draft.selected === null}
      busy={false}
      onToggle={(id) => {
        const next = toggleId(activeIds, id, pickerIds);
        const all = next.length === pickerIds.length;
        props.onChange({ ...draft, selected: all ? null : next });
      }}
      onShowAll={() => props.onChange({ ...draft, selected: null })}
      onClearAll={() => props.onChange({ ...draft, selected: [] })}
    />
  );
}
