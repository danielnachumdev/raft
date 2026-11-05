/** Copy for Settings → Check for updates (PII-free). */

export function updateConfirmMessage(from: string, to: string): string {
  return (
    `Install the latest release on this host. ` +
    `Installed ${from} → ${to}. ` +
    `Afterward, Redeploy the always-on dashboard so it picks up the new version.`
  );
}

export function updateSuccessMessage(result: {
  alreadyCurrent: boolean;
  beforeLine: string | null;
  afterLine: string | null;
}): string {
  if (result.alreadyCurrent) {
    const line = result.afterLine || result.beforeLine;
    return line
      ? `Already up to date (${line}).`
      : "Already up to date.";
  }
  const before = result.beforeLine || "(unknown)";
  const after = result.afterLine || "(unknown)";
  return `Updated: ${before} → ${after}`;
}

export function updateFailureMessage(_detail: string): string {
  return "Update failed. Try again later.";
}
