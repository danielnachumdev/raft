/** Operator copy for the Settings temporary-override (GitOps) warning. */

export const TEMPORARY_OVERRIDE_TITLE = "Temporary host override";

export function temporaryOverrideLead(): string {
  return (
    "Edits here write host/settings.yaml on this host for live testing only. " +
    "The next GitOps deploy (vpsctl Sync host config / when host/settings.yaml " +
    "is synced from the ops repo) will wipe and replace these changes."
  );
}

export function temporaryOverrideGuidance(): string {
  return (
    "Durable settings belong in the GitOps repo (vpsctl host/settings.yaml), " +
    "not click-ops. Later, only privileged RBAC roles may use this escape hatch."
  );
}

/** Toast after a successful Save — every SPA write is a host-local override. */
export function temporaryOverrideSavedMessage(): string {
  return (
    "Temporary host override saved. Next GitOps sync will replace " +
    "host/settings.yaml."
  );
}
