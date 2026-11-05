export type ReconcileResult = {
  selected: string[] | null;
  /** Saved service/group ids missing from the live catalog. */
  missingIds: string[];
};

/**
 * Intersect a saved selection with live picker ids at render time.
 * The stored graph is left untouched so ids that return (e.g. a service
 * coming back into the window) reappear without re-editing.
 */
export function reconcileSelection(
  selected: string[] | null,
  availableIds: string[],
): ReconcileResult {
  if (selected === null || availableIds.length === 0) {
    return { selected, missingIds: [] };
  }
  const live = new Set(availableIds);
  return {
    selected: selected.filter((id) => live.has(id)),
    missingIds: selected.filter((id) => !live.has(id)),
  };
}

/** Short operator notice when a graph referenced removed services/groups. */
export function staleSelectionMessage(
  missingIds: string[],
  groupMode: boolean,
): string | null {
  if (missingIds.length === 0) return null;
  const noun = groupMode ? "group" : "service";
  const plural = missingIds.length === 1 ? noun : `${noun}s`;
  return `${missingIds.length} saved ${plural} no longer available.`;
}
