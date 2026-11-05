import { useMemo, useState } from "react";

export function IdFilter(props: {
  title: string;
  searchLabel: string;
  searchPlaceholder: string;
  emptyLabel: string;
  items: { id: string; label: string }[];
  activeIds: string[];
  showingAll: boolean;
  busy: boolean;
  onToggle: (id: string) => void;
  onShowAll: () => void;
  onClearAll: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return props.items;
    return props.items.filter(
      (a) =>
        a.label.toLowerCase().includes(q) || a.id.toLowerCase().includes(q),
    );
  }, [props.items, query]);
  const noneSelected = props.activeIds.length === 0;

  return (
    <div className="trends-services-block">
      <div className="trends-services-head">
        <span className="trends-services-title">{props.title}</span>
        <div className="trends-services-actions">
          <button
            type="button"
            className="trends-clear-all"
            onClick={props.onClearAll}
            disabled={props.busy || noneSelected || props.items.length === 0}
          >
            Clear all
          </button>
          <button
            type="button"
            className="trends-show-all"
            onClick={props.onShowAll}
            disabled={
              props.busy || props.showingAll || props.items.length === 0
            }
          >
            Show all
          </button>
        </div>
      </div>
      <input
        type="search"
        className="trends-services-search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={props.searchPlaceholder}
        aria-label={props.searchLabel}
        disabled={props.busy}
      />
      <div
        className="trends-services-list"
        role="group"
        aria-label={props.title}
      >
        {filtered.length === 0 ? (
          <p className="muted trends-services-empty">{props.emptyLabel}</p>
        ) : (
          filtered.map((a) => (
            <label key={a.id} className="trends-chip">
              <input
                type="checkbox"
                checked={props.activeIds.includes(a.id)}
                onChange={() => props.onToggle(a.id)}
                disabled={props.busy}
              />
              <span className="trends-chip-label">{a.label}</span>
            </label>
          ))
        )}
      </div>
    </div>
  );
}
