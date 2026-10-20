import type { MouseEvent } from "react";

/**
 * Id of the last section whose top edge has scrolled above ``offset``.
 * At the bottom of the page the last section wins (short tails never reach the top).
 */
export function activeSectionId(
  tops: { id: string; top: number }[],
  offset: number,
  atBottom = false,
): string | null {
  if (atBottom && tops.length) return tops[tops.length - 1].id;
  let active: string | null = null;
  for (const entry of tops) {
    if (entry.top - offset <= 0) active = entry.id;
  }
  return active ?? tops[0]?.id ?? null;
}

/** In-page anchor click: smooth-scroll and update the hash without a jump. */
export function jumpToSection(event: MouseEvent, id: string): void {
  const target = document.getElementById(id);
  if (!target) return;
  event.preventDefault();
  target.scrollIntoView({ behavior: "smooth", block: "start" });
  window.history.replaceState(window.history.state, "", `#${id}`);
}
