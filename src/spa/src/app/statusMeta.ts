export function statusMetaLabel(opts: {
  updating: boolean;
  fetchedAt: number | null;
  now: number;
}): string | null {
  if (opts.updating) return "Updating…";
  if (opts.fetchedAt === null) return null;
  return formatUpdatedAgo(opts.fetchedAt, opts.now);
}

function formatUpdatedAgo(fetchedAt: number, now: number): string {
  const sec = Math.max(0, Math.floor((now - fetchedAt) / 1000));
  if (sec < 5) return "Updated just now";
  if (sec < 60) return `Updated ${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `Updated ${min}m ago`;
  return `Updated ${Math.floor(min / 60)}h ago`;
}
