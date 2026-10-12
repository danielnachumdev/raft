import type { ReactNode, RefObject } from "react";
import type { LogFilter } from "./model/logFilter";
import { LogFilterBar } from "./LogFilterBar";
import { LogLines } from "./LogLines";
import type { ParsedLogLine } from "./model/logParse";

const NEAR_BOTTOM_PX = 48;

/** Error / loading / filter / scrollable lines for LogViewer. */
export function LogViewerBody(props: {
  error: string | null;
  connecting: boolean;
  connectingLabel: string;
  showStream: boolean;
  filter: LogFilter;
  onFilterChange: (next: LogFilter) => void;
  matchCount: number;
  totalCount: number;
  viewRef: RefObject<HTMLDivElement | null>;
  onStick: (near: boolean) => void;
  lines: ParsedLogLine[];
  highlightValues: string[];
  emptyLabel: string;
}) {
  return (
    <>
      {props.error ? (
        <p className="error" role="alert">
          {props.error}
        </p>
      ) : null}
      {props.connecting ? (
        <div className="logs-loading" role="status" aria-busy="true">
          <span className="spinner refresh-spinner" aria-hidden="true" />
          <span>{props.connectingLabel}</span>
        </div>
      ) : null}
      {props.showStream ? (
        <>
          <LogFilterBar
            filter={props.filter}
            matchCount={props.matchCount}
            totalCount={props.totalCount}
            onChange={props.onFilterChange}
          />
          <div
            className="logs-view"
            ref={props.viewRef}
            onScroll={(e) => props.onStick(isNearBottom(e.currentTarget))}
          >
            <LogLines
              lines={props.lines}
              highlightValues={props.highlightValues}
              emptyLabel={props.emptyLabel}
            />
          </div>
        </>
      ) : null}
    </>
  );
}

/** Inline panel vs fullscreen overlay chrome. */
export function LogViewerShell(props: {
  title: string;
  overlayTitle: string;
  expanded: boolean;
  controls: ReactNode;
  body: ReactNode;
}) {
  if (!props.expanded) {
    return (
      <section className="panel logs-panel">
        <div className="panel-head">
          <h2>{props.title}</h2>
          {props.controls}
        </div>
        {props.body}
      </section>
    );
  }
  return (
    <>
      <section
        className="panel logs-panel logs-panel-placeholder"
        aria-hidden="true"
      >
        <div className="panel-head">
          <h2>{props.title}</h2>
        </div>
      </section>
      <div
        className="logs-overlay"
        role="dialog"
        aria-modal="true"
        aria-label={props.overlayTitle}
      >
        <div className="logs-overlay-panel">
          <div className="panel-head">
            <h2>{props.overlayTitle}</h2>
            {props.controls}
          </div>
          {props.body}
          <p className="logs-overlay-hint muted">Press Esc to collapse</p>
        </div>
      </div>
    </>
  );
}

function isNearBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_PX;
}
