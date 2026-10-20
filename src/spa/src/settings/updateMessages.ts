/** Copy for Settings → Check for updates (PII-free). */

export function updateConfirmMessage(from: string, to: string): string {
  return (
    `Reinstall the host raft CLI from the latest GitHub Release wheel ` +
    `(same path as \`raft update\` / install.sh). ` +
    `Installed ${from} → ${to}. ` +
    `Afterward, recreate the always-on dashboard so its image picks up the new stamp.`
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
      ? `raft is already up to date (${line}).`
      : "raft is already up to date.";
  }
  const before = result.beforeLine || "(unknown)";
  const after = result.afterLine || "(unknown)";
  return `Updated: ${before} → ${after}`;
}

export function updateFailureMessage(detail: string): string {
  return `Update failed: ${detail}`;
}
