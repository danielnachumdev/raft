import type { ReactNode } from "react";

/** Sticky footer shown while a page has unsaved edits: Discard + Save. */
export function SaveBar(props: {
  open: boolean;
  message?: ReactNode;
  saveLabel: string;
  saving: boolean;
  disabled?: boolean;
  onSave: () => void;
  onDiscard: () => void;
  id?: string;
}) {
  if (!props.open) return null;
  return (
    <div className="save-bar" role="status" id={props.id}>
      <p className="save-bar-text">{props.message ?? "Unsaved changes"}</p>
      <div className="btn-group">
        <button
          type="button"
          className="btn btn-ghost"
          disabled={props.saving}
          onClick={props.onDiscard}
        >
          Discard
        </button>
        <button
          type="button"
          className={props.saving ? "btn btn-primary is-loading" : "btn btn-primary"}
          disabled={props.saving || props.disabled}
          aria-busy={props.saving}
          onClick={props.onSave}
        >
          {props.saving ? (
            <span className="spinner btn-spinner" aria-hidden="true" />
          ) : null}
          {props.saveLabel}
        </button>
      </div>
    </div>
  );
}
