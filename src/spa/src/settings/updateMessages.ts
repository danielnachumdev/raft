/** Copy for Settings → Check for updates (PII-free). */

export function updateConfirmMessage(from: string, to: string): string {
  return (
    `Reinstall raft from the latest GitHub Release wheel ` +
    `(same path as \`raft update\`). ` +
    `Installed ${from} → ${to}. ` +
    `Brief service impact is possible while the CLI package is replaced.`
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
