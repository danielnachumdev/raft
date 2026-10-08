import { useEffect, useRef, useState } from "react";
import { Modal } from "./Modal";
import "./ConfirmPopup.css";
export type ConfirmPopupProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Emphasize destructive confirm (stop). */
  danger?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
};

/** Confirm / cancel popup built on Modal; awaits async onConfirm. */
export function ConfirmPopup(props: ConfirmPopupProps) {
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  const confirmLabel = props.confirmLabel ?? "Confirm";
  const cancelLabel = props.cancelLabel ?? "Cancel";

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  return (
    <Modal
      open={props.open}
      onClose={busy ? noop : props.onCancel}
      title={props.title}
      closeOnOverlay={!busy}
      footer={
        <div className="modal-actions">
          <button
            type="button"
            className="action-btn"
            disabled={busy}
            onClick={props.onCancel}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={[
              "action-btn",
              props.danger ? "action-btn-danger" : "",
              busy ? "is-loading" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            disabled={busy}
            aria-busy={busy}
            onClick={() => void handleConfirm()}
          >
            {busy ? (
              <span className="spinner refresh-spinner" aria-hidden="true" />
            ) : null}
            {confirmLabel}
          </button>
        </div>
      }
    >
      <p className="modal-message">{props.message}</p>
    </Modal>
  );

  async function handleConfirm() {
    setBusy(true);
    try {
      await props.onConfirm();
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
}

function noop() {}
