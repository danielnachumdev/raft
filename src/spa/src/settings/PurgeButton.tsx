import { useState } from "react";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { toast } from "../chrome/toast";
import { postPurge } from "../shared/api";
import {
  purgeFailureMessage,
  purgeStartedMessage,
  purgeSuccessMessage,
} from "./purgeMessages";
import "./PurgeButton.css";

/** Settings → Storage: confirm, then background POST /api/purge with toasts. */
export function PurgeButton() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  return (
    <>
      <button
        type="button"
        className={busy ? "btn is-loading" : "btn"}
        onClick={() => setOpen(true)}
        disabled={busy}
        aria-busy={busy}
        aria-label="Purge unused Docker images"
        title="Remove unused Docker images and build cache"
        id="stack-purge"
      >
        {busy ? (
          <span className="spinner btn-spinner" aria-hidden="true" />
        ) : null}
        Purge unused images
      </button>
      <ConfirmPopup
        open={open}
        title="Purge unused images?"
        message={
          "Removes Docker images not used by any container and unused " +
          "build cache. Images still attached to running or stopped " +
          "containers are kept. Volumes (App data) are not touched."
        }
        confirmLabel="Purge"
        danger={false}
        onCancel={() => setOpen(false)}
        onConfirm={() => startPurge()}
      />
    </>
  );

  /** Dismiss confirm immediately; purge runs in the background with toasts. */
  function startPurge() {
    setOpen(false);
    if (busy) return;
    setBusy(true);
    toast.regular(purgeStartedMessage());
    void runPurge();
  }

  async function runPurge() {
    try {
      const result = await postPurge();
      toast.good(purgeSuccessMessage(result.reclaimed_human));
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Purge failed.";
      toast.bad(purgeFailureMessage(detail));
    } finally {
      setBusy(false);
    }
  }
}
