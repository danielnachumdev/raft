import { useState, type FormEvent } from "react";
import { EVENT_KIND_GROUPS, type EventsQuery } from "./eventsView";

const HOUR_OPTIONS: { value: number; label: string }[] = [
  { value: 1, label: "Last hour" },
  { value: 6, label: "Last 6 hours" },
  { value: 24, label: "Last 24 hours" },
  { value: 72, label: "Last 3 days" },
  { value: 168, label: "Last 7 days" },
];

/** Window / kind / service toolbar; range and kind apply on change, service on submit. */
export function EventsFilters(props: {
  query: EventsQuery;
  services: string[];
  onChange: (next: EventsQuery) => void;
}) {
  const { query, onChange } = props;
  const [service, setService] = useState(query.service);
  const dirty = service.trim() !== query.service;
  const filtered = query.kind !== "" || query.service !== "";

  return (
    <form className="toolbar events-filters" id="events-filters" onSubmit={submit}>
      <label className="field-caps">
        Window
        <select
          id="events-hours"
          value={query.hours}
          onChange={(e) => onChange({ ...query, hours: Number(e.target.value) })}
        >
          {HOUR_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <label className="field-caps">
        Kind
        <select
          id="events-kind"
          value={query.kind}
          onChange={(e) => onChange({ ...query, kind: e.target.value })}
        >
          <option value="">All kinds</option>
          {EVENT_KIND_GROUPS.map((group) => (
            <optgroup key={group.label} label={group.label}>
              {group.kinds.map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <label className="field-caps events-filter-service">
        Service
        <input
          id="events-service"
          type="search"
          placeholder="All services"
          value={service}
          list="events-service-suggestions"
          autoComplete="off"
          onChange={(e) => setService(e.target.value)}
        />
        <datalist id="events-service-suggestions">
          {props.services.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </label>
      <div className="btn-group events-filter-actions">
        <button
          type="submit"
          className="btn btn-primary"
          id="events-apply-filters"
          disabled={!dirty}
        >
          Apply
        </button>
        {filtered ? (
          <button type="button" className="btn btn-ghost" id="events-clear" onClick={clear}>
            Clear filters
          </button>
        ) : null}
      </div>
    </form>
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    onChange({ ...query, service: service.trim() });
  }

  function clear() {
    setService("");
    onChange({ ...query, kind: "", service: "" });
  }
}
