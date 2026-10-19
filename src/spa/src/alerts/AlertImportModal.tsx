import { useState } from "react";
import { Modal } from "../chrome/Modal";
import type { AlertRule } from "./alertsHelpers";

/** Choose merge vs replace for an imported rules document. */
export function AlertImportModal(props: {
  fileName: string;
  rules: AlertRule[];
  existing: number;
  onCancel: () => void;
  onImport: (prune: boolean) => Promise<void>;
}) {
  const [busy, setBusy] = useState<"merge" | "replace" | null>(null);
  const run = async (prune: boolean) => {
    setBusy(prune ? "replace" : "merge");
    try {
      await props.onImport(prune);
    } finally {
      setBusy(null);
    }
  };
  return (
    <Modal
      open
      title="Import alert rules"
      onClose={busy ? noop : props.onCancel}
      closeOnOverlay={!busy}
      footer={
        <div className="modal-actions">
          <button type="button" className="btn" disabled={!!busy} onClick={props.onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            id="alerts-import-replace"
            disabled={!!busy}
            onClick={() => void run(true)}
          >
            {busy === "replace" ? <span className="spinner refresh-spinner" aria-hidden="true" /> : null}
            Replace all
          </button>
          <button
            type="button"
            className="btn btn-primary"
            id="alerts-import-merge"
            disabled={!!busy}
            onClick={() => void run(false)}
          >
            {busy === "merge" ? <span className="spinner refresh-spinner" aria-hidden="true" /> : null}
            Merge
          </button>
        </div>
      }
    >
      <p className="modal-message">
        <code>{props.fileName}</code> has {props.rules.length} rule
        {props.rules.length === 1 ? "" : "s"}. <strong>Merge</strong> adds or updates them and
        keeps your other {props.existing} rule{props.existing === 1 ? "" : "s"}.{" "}
        <strong>Replace all</strong> also deletes rules that are not in the file.
      </p>
    </Modal>
  );
}

function noop() {}
