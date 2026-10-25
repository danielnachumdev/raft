import type { ReactNode } from "react";
import { toast } from "../chrome/toast";
import type { RecommendationItem } from "./types";

export type RecommendationListProps<T extends RecommendationItem> = {
  items: T[];
  busy?: boolean;
  sectionId?: string;
  heading?: string;
  lede?: string;
  applyLabel?: string;
  dismissLabel?: string;
  applyIdPrefix?: string;
  dismissIdPrefix?: string;
  onApply: (item: T) => void | Promise<void>;
  onDismiss: (id: string) => Promise<void>;
  renderPreview?: (item: T) => ReactNode;
};

/** Generic recommendations panel: title, reason, optional preview, apply/dismiss. */
export function RecommendationList<T extends RecommendationItem>(
  props: RecommendationListProps<T>,
) {
  if (props.items.length === 0) return null;

  const sectionId = props.sectionId ?? "recommendations";
  const applyPrefix = props.applyIdPrefix ?? `${sectionId}-apply`;
  const dismissPrefix = props.dismissIdPrefix ?? `${sectionId}-dismiss`;

  async function dismiss(id: string) {
    try {
      await props.onDismiss(id);
      toast.good("Recommendation dismissed");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Dismiss failed");
    }
  }

  async function apply(item: T) {
    try {
      await props.onApply(item);
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Apply failed");
    }
  }

  return (
    <section className="panel" id={sectionId}>
      <div className="panel-head">
        <h2>
          {props.heading ?? "Recommendations"}
          <span className="panel-count">{props.items.length}</span>
        </h2>
      </div>
      {props.lede ? <p className="panel-lede">{props.lede}</p> : null}
      <ul className="item-list">
        {props.items.map((item) => (
          <li key={item.id} className="item-row" data-rec-id={item.id}>
            <div className="item-row-main">
              <div className="item-row-title">
                <strong>{item.title}</strong>
              </div>
              <p className="item-row-meta">{item.summary}</p>
              {props.renderPreview ? (
                <p className="item-row-meta">{props.renderPreview(item)}</p>
              ) : null}
            </div>
            <div className="btn-group item-row-actions">
              <button
                type="button"
                className="btn btn-sm"
                id={`${applyPrefix}-${item.id}`}
                disabled={props.busy}
                onClick={() => void apply(item)}
              >
                {props.applyLabel ?? "Apply"}
              </button>
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                id={`${dismissPrefix}-${item.id}`}
                disabled={props.busy}
                onClick={() => void dismiss(item.id)}
              >
                {props.dismissLabel ?? "Dismiss"}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
