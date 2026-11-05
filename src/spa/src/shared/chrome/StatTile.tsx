import type { ReactNode } from "react";
import "./StatTile.css";

export type StatTileTone = "ok" | "warn" | "bad" | "idle";

/** Grid wrapper for StatTile items. */
export function StatTiles(props: {
  label: string;
  id?: string;
  children: ReactNode;
}) {
  return (
    <ul className="stat-tiles" id={props.id} aria-label={props.label}>
      {props.children}
    </ul>
  );
}

/** Label / big value / optional hint card. */
export function StatTile(props: {
  label: string;
  value: ReactNode;
  tone?: StatTileTone;
  hint?: ReactNode;
}) {
  return (
    <li className={props.tone ? `stat-tile stat-tile--${props.tone}` : "stat-tile"}>
      <span className="stat-tile-label">{props.label}</span>
      <span className="stat-tile-value">{props.value}</span>
      {props.hint ? <span className="stat-tile-hint">{props.hint}</span> : null}
    </li>
  );
}
