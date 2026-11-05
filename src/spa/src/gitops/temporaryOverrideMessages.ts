/** Operator copy for temporary host overrides of GitOps flat docs. */

export type GitopsHostDoc =
  | "settings.yaml"
  | "firewall.yaml"
  | "alerts.yaml"
  | "notifications.yaml";

export const TEMPORARY_OVERRIDE_TITLE = "Temporary host override";

export function temporaryOverrideLead(doc: GitopsHostDoc): string {
  return (
    `Edits here write host/${doc} on this host for live testing only. ` +
    `The next GitOps deploy (vpsctl Sync host config / when host/${doc} ` +
    "is synced from the ops repo) will wipe and replace these changes."
  );
}

export function temporaryOverrideGuidance(doc: GitopsHostDoc): string {
  return (
    `Durable config belongs in the GitOps repo (vpsctl host/${doc}), ` +
    "not click-ops. Later, only privileged RBAC roles may use this escape hatch."
  );
}

/** Toast after a successful Save — every SPA write is a host-local override. */
export function temporaryOverrideSavedMessage(doc: GitopsHostDoc): string {
  return (
    "Temporary host override saved. Next GitOps sync will replace " +
    `host/${doc}.`
  );
}

export function unsavedTemporaryOverrideMessage(): string {
  return "Unsaved temporary override — next GitOps sync will replace it";
}

/** Durable tip-dismissal snippet for firewall / alerts GitOps docs. */
export function disableTipsYamlSnippet(): string {
  return "disable_tips: true\n";
}

/** Toast after dismissing a recommendation (host-local, not GitOps SoT). */
export function temporaryTipsDismissMessage(
  doc: Extract<GitopsHostDoc, "firewall.yaml" | "alerts.yaml">,
): string {
  return (
    "Tip dismiss is temporary. For a lasting hide, set disable_tips: true " +
    `on host/${doc} in the GitOps repo, then Sync.`
  );
}
