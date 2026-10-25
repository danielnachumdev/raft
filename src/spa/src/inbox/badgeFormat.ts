/** Client-side badge text for unread counts (mirrors server ``InboxBadge``). */

export const BADGE_CAP = 99;
export const BADGE_OVERFLOW = "+99";

/** Format unread count for the bell badge; null hides the badge. */
export function formatInboxBadge(count: number): string | null {
  if (count <= 0) return null;
  if (count > BADGE_CAP) return BADGE_OVERFLOW;
  return String(count);
}
