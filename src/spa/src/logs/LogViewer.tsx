import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  defaultLogFilter,
  filterLogLines,
  isLogFilterActive,
} from "./model/logFilter";
import { LogViewerBody, LogViewerShell } from "./LogViewerLayout";
import { parseLogText } from "./model/logParse";
import "./LogViewer.css";

/** Shared log panel: filter + lines + expand. Parents supply the text stream. */
export function LogViewer(props: {
  title: string;
  overlayTitle: string;
  text: string;
  busy: boolean;
  error: string | null;
  connectingLabel: string;
  controls: ReactNode;
}) {
  const [filter, setFilter] = useState(defaultLogFilter);
  const [expanded, setExpanded] = useState(false);
  const [stick, setStick] = useState(true);
  const viewRef = useRef<HTMLDivElement>(null);
  const lines = useMemo(() => parseLogText(props.text), [props.text]);
  const visible = useMemo(() => filterLogLines(lines, filter), [lines, filter]);
  const connecting = props.busy && props.text === "" && !props.error;

  useEffect(() => {
    const el = viewRef.current;
    if (!el || !stick) return;
    el.scrollTop = el.scrollHeight;
  }, [props.text, stick, filter]);

  useExpandEscape(expanded, () => setExpanded(false));

  const body = (
    <LogViewerBody
      error={props.error}
      connecting={connecting}
      connectingLabel={props.connectingLabel}
      showStream={props.text !== "" || (!props.busy && !props.error)}
      filter={filter}
      onFilterChange={setFilter}
      matchCount={visible.length}
      totalCount={lines.length}
      viewRef={viewRef}
      onStick={setStick}
      lines={visible}
      highlightValues={filter.values}
      emptyLabel={
        isLogFilterActive(filter)
          ? "No lines match this filter."
          : "(no log output)"
      }
    />
  );

  const controls = (
    <div className="logs-controls">
      {props.controls}
      <button
        type="button"
        className="action-btn"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? "Collapse" : "Expand"}
      </button>
    </div>
  );

  return (
    <LogViewerShell
      title={props.title}
      overlayTitle={props.overlayTitle}
      expanded={expanded}
      controls={controls}
      body={body}
    />
  );
}

function useExpandEscape(expanded: boolean, onCollapse: () => void): void {
  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCollapse();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [expanded, onCollapse]);
}
