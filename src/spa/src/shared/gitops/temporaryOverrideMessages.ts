/** Operator copy for temporary host-side edits (no paths or sync how-to). */

export type GitopsHostDoc =
  | "settings.yaml"
  | "firewall.yaml"
  | "alerts.yaml"
  | "notifications.yaml"
  | "rbac.yaml";

export const TEMPORARY_OVERRIDE_TITLE = "Temporary changes";

export function temporaryOverrideLead(_doc?: GitopsHostDoc): string {
  return "Changes saved here apply on this host only.";
}

export function temporaryOverrideSavedMessage(_doc?: GitopsHostDoc): string {
  return "Saved. These changes may be replaced later.";
}

export function unsavedTemporaryOverrideMessage(): string {
  return "Unsaved changes";
}

/** Toast after dismissing a recommendation. */
export function temporaryTipsDismissMessage(
  _doc?: Extract<GitopsHostDoc, "firewall.yaml" | "alerts.yaml">,
): string {
  return "Tip dismissed.";
}
