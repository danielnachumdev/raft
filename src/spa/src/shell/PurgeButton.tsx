import { useState } from "react";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { toast } from "../chrome/toast";
import { postPurge } from "../shared/api";
import "./PurgeButton.css";

/** Dashboard control: confirm, then POST /api/purge and toast reclaim. */
export function PurgeButton() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  return (
    <>
      <button
        type="button"
        className={busy ? "refresh is-loading" : "refresh"}
        onClick={() => setOpen(true)}
        disabled={busy}
        aria-busy={busy}
        aria-label="Purge unused Docker images"
        id="stack-purge"
      >
        {busy ? (
          <span className="spinner refresh-spinner" aria-hidden="true" />
        ) : null}
        Purge
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
        onConfirm={() => runPurge()}
      />
    </>
  );

  async function runPurge() {
    setBusy(true);
    try {
      const result = await postPurge();
      toast.good(successMessage(result.reclaimed_human));
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Purge failed.";
      toast.bad(`Purge failed: ${detail}`);
    } finally {
      setBusy(false);
      setOpen(false);
    }
  }
}

function successMessage(human: string): string {
  if (!human || human === "0B" || human === "-") {
    return "Purge finished — nothing to reclaim (0B).";
  }
  return `Purge finished — reclaimed ${human}.`;
}
