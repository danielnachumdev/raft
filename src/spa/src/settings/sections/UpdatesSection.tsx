import { useState } from "react";
import { ConfirmPopup } from "../../chrome/ConfirmPopup";
import { toast } from "../../chrome/toast";
import { SectionCard } from "../SectionCard";
import {
  applyUpdate,
  fetchUpdateStatus,
  type UpdateApplyResult,
  type UpdateStatus,
} from "../updateApi";
import {
  updateConfirmMessage,
  updateFailureMessage,
  updateSuccessMessage,
} from "../updateMessages";
import "./UpdatesSection.css";

type Phase =
  | "idle"
  | "checking"
  | "checked"
  | "updating"
  | "success"
  | "error";

/** Settings control: check GitHub latest Release and run ``raft update``. */
export function UpdatesSection() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [result, setResult] = useState<UpdateApplyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const busy = phase === "checking" || phase === "updating";

  return (
    <SectionCard
      id="settings-updates"
      title="Updates"
      hint="Same source of truth as raft update / install.sh — latest GitHub Release wheel."
    >
      <div className="settings-updates">
        <p className="settings-updates-status" id="settings-updates-status">
          {statusLabel(phase, status, result, error)}
        </p>
        {result?.nextSteps ? (
          <p className="muted settings-updates-next" id="settings-updates-next">
            {result.nextSteps}
          </p>
        ) : null}
        <div className="settings-updates-actions">
          <button
            type="button"
            className="btn-secondary"
            id="settings-check-updates"
            disabled={busy}
            onClick={() => void runCheck()}
          >
            {phase === "checking" ? "Checking…" : "Check for updates"}
          </button>
          {status?.updateAvailable ? (
            <button
              type="button"
              className="btn-primary"
              id="settings-apply-update"
              disabled={busy}
              onClick={() => setConfirmOpen(true)}
            >
              Update raft
            </button>
          ) : null}
        </div>
      </div>
      <ConfirmPopup
        open={confirmOpen}
        title="Update raft?"
        message={updateConfirmMessage(
          status?.current ?? "?",
          status?.latestVersion ?? status?.latestTag ?? "latest",
        )}
        confirmLabel="Update raft"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => runApply()}
      />
    </SectionCard>
  );

  async function runCheck() {
    setPhase("checking");
    setError(null);
    setResult(null);
    try {
      setStatus(await fetchUpdateStatus());
      setPhase("checked");
    } catch (err) {
      fail(err, "Failed to check for updates", false);
    }
  }

  async function runApply() {
    setPhase("updating");
    setError(null);
    try {
      const outcome = await applyUpdate();
      setResult(outcome);
      setPhase("success");
      setConfirmOpen(false);
      toast.good(updateSuccessMessage(outcome));
      await refreshStatus();
    } catch (err) {
      fail(err, "Update failed", true);
    }
  }

  async function refreshStatus() {
    const refreshed = await fetchUpdateStatus().catch(() => null);
    if (refreshed) setStatus(refreshed);
  }

  function fail(err: unknown, fallback: string, asUpdate: boolean) {
    const detail = err instanceof Error ? err.message : fallback;
    setError(detail);
    setPhase("error");
    toast.bad(asUpdate ? updateFailureMessage(detail) : detail);
  }
}

function statusLabel(
  phase: Phase,
  status: UpdateStatus | null,
  result: UpdateApplyResult | null,
  error: string | null,
): string {
  if (phase === "checking") return "Checking GitHub for the latest Release…";
  if (phase === "updating") return "Updating raft (install.sh / Release wheel)…";
  if (phase === "error" && error) return error;
  if (phase === "success" && result) return updateSuccessMessage(result);
  if (status) return status.message;
  return "Check whether a newer raft Release is available on this host.";
}
