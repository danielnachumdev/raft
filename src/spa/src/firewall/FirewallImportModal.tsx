import { useState } from "react";
import { Modal } from "../chrome/Modal";
import { toast } from "../chrome/toast";

/** Paste an exported firewall JSON document; Import replaces + applies. */
export function FirewallImportModal(props: {
  open: boolean;
  onClose: () => void;
  onImport: (body: unknown) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    try {
      await props.onImport(JSON.parse(text) as unknown);
      props.onClose();
      setText("");
      toast.good("Firewall imported (gate nginx reload)");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={props.open}
      onClose={busy ? () => undefined : props.onClose}
      title="Import firewall"
      closeOnOverlay={!busy}
      footer={
        <div className="modal-actions">
          <button type="button" className="btn" disabled={busy} onClick={props.onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            id="firewall-import-confirm"
            disabled={busy || !text.trim()}
            onClick={() => void confirm()}
          >
            Import &amp; apply
          </button>
        </div>
      }
    >
      <p className="muted">
        Paste a JSON document with version and rules (export format). Importing
        replaces the current table and reloads the gate.
      </p>
      <textarea
        id="firewall-import-text"
        className="fw-import-area"
        value={text}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
      />
    </Modal>
  );
}
