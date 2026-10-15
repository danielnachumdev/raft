import type { TrendsViewConfig } from "./types.ts";

export type ReconcileResult = {
  config: TrendsViewConfig;
  /** Saved service/group ids missing from the live catalog. */
  missingIds: string[];
};

/**
 * Apply a saved view against live picker ids.
 * Drops stale selection ids; leaves metrics / mode / range intact.
 */
export function reconcileViewConfig(
  config: TrendsViewConfig,
  availableIds: string[],
): ReconcileResult {
  if (config.selected === null) {
    return { config, missingIds: [] };
  }
  const live = new Set(availableIds);
  const missingIds = config.selected.filter((id) => !live.has(id));
  const selected = config.selected.filter((id) => live.has(id));
  return {
    config: { ...config, selected },
    missingIds,
  };
}

/** Short operator notice when a view referenced removed services/groups. */
export function staleSelectionMessage(
  missingIds: string[],
  groupMode: boolean,
): string | null {
  if (missingIds.length === 0) return null;
  const noun = groupMode ? "group" : "service";
  const plural = missingIds.length === 1 ? noun : `${noun}s`;
  return `${missingIds.length} saved ${plural} no longer available.`;
}
