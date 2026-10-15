import { useState } from "react";
import { ConfirmPopup } from "../../chrome/ConfirmPopup";
import type { NamedTrendsView, TrendsViewsStore } from "./types.ts";
import { TrendsViewNameModal } from "./TrendsViewNameModal";
import "./TrendsViewsBar.css";

const EXPLORER = "";

export function TrendsViewsBar(props: {
  store: TrendsViewsStore;
  staleMessage: string | null;
  onSelect: (viewId: string | null) => void;
  onSave: (name: string) => void;
  onUpdate: () => void;
  onRename: (name: string) => void;
  onDelete: () => void;
}) {
  const [saveOpen, setSaveOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const active = activeView(props.store);
  const selectValue = active?.id ?? EXPLORER;

  return (
    <div className="trends-views">
      <label className="trends-field">
        <span>Saved view</span>
        <select
          value={selectValue}
          onChange={(e) => {
            const v = e.target.value;
            props.onSelect(v === EXPLORER ? null : v);
          }}
          aria-label="Saved Trends view"
        >
          <option value={EXPLORER}>Explorer</option>
          {props.store.views.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
      </label>
      <div className="trends-views-actions">
        <button
          type="button"
          className="action-btn"
          onClick={() => setSaveOpen(true)}
        >
          Save…
        </button>
        {active ? (
          <>
            <button
              type="button"
              className="action-btn"
              onClick={props.onUpdate}
            >
              Update
            </button>
            <button
              type="button"
              className="action-btn"
              onClick={() => setRenameOpen(true)}
            >
              Rename…
            </button>
            <button
              type="button"
              className="action-btn action-btn-danger"
              onClick={() => setDeleteOpen(true)}
            >
              Delete
            </button>
          </>
        ) : null}
      </div>
      {props.staleMessage ? (
        <p className="muted trends-views-stale" role="status">
          {props.staleMessage}
        </p>
      ) : null}
      <TrendsViewNameModal
        open={saveOpen}
        title="Save Trends view"
        initialName={suggestName(props.store.views)}
        confirmLabel="Save"
        onCancel={() => setSaveOpen(false)}
        onConfirm={(name) => {
          props.onSave(name);
          setSaveOpen(false);
        }}
      />
      <TrendsViewNameModal
        open={renameOpen}
        title="Rename Trends view"
        initialName={active?.name ?? ""}
        confirmLabel="Rename"
        onCancel={() => setRenameOpen(false)}
        onConfirm={(name) => {
          props.onRename(name);
          setRenameOpen(false);
        }}
      />
      <ConfirmPopup
        open={deleteOpen}
        title="Delete Trends view"
        message={
          active
            ? `Delete “${active.name}”? This only removes the saved view in this browser.`
            : "Delete this view?"
        }
        confirmLabel="Delete"
        danger
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => {
          props.onDelete();
          setDeleteOpen(false);
        }}
      />
    </div>
  );
}

function activeView(store: TrendsViewsStore): NamedTrendsView | null {
  if (!store.activeId) return null;
  return store.views.find((v) => v.id === store.activeId) ?? null;
}

function suggestName(views: NamedTrendsView[]): string {
  const n = views.length + 1;
  return `View ${n}`;
}
