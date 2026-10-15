/** Shown when the open dashboard has no graphs. */
export function DashboardEmpty(props: {
  onAdd: () => void;
  onRestoreDefaults: () => void;
}) {
  return (
    <div className="empty-state trends-dash-empty" id="trends-empty">
      <div className="trends-dash-empty-art" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>
      <p>
        <strong>No graphs on this dashboard.</strong>
      </p>
      <p className="muted">
        Add a graph from a preset (CPU, latency, errors…) or start from the
        default overview layout.
      </p>
      <div className="trends-dash-empty-actions">
        <button type="button" className="action-btn btn-primary" onClick={props.onAdd}>
          + Add graph
        </button>
        <button type="button" className="action-btn" onClick={props.onRestoreDefaults}>
          Use default graphs
        </button>
      </div>
    </div>
  );
}
