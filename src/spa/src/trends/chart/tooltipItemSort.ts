/** Payload fields Recharts passes to Tooltip ``itemSorter`` (lodash sortBy). */
export type TooltipSortItem = {
  value?: number | string | Array<number | string>;
  name?: number | string;
};

/** Absolute finite magnitude for sorting; non-finite → -1 (sorts last). */
export function tooltipItemMagnitude(item: TooltipSortItem): number {
  const raw = Array.isArray(item.value) ? item.value[0] : item.value;
  const n = Math.abs(Number(raw));
  return Number.isFinite(n) ? n : -1;
}

/**
 * Lodash sortBy key: abs(value) desc, then name asc.
 * Milli-scaled magnitude fits percent fractions; fixed-width invert stays
 * ordered for byte-scale values (Network RX / memory / block I/O).
 */
export function tooltipItemSortKey(item: TooltipSortItem): string {
  const mag = tooltipItemMagnitude(item);
  const scaled =
    mag < 0
      ? -1
      : Math.min(Math.round(mag * 1000), Number.MAX_SAFE_INTEGER);
  const inverted =
    scaled < 0
      ? Number.MAX_SAFE_INTEGER + 1
      : Number.MAX_SAFE_INTEGER - scaled;
  return `${String(inverted).padStart(16, "0")}\0${String(item.name ?? "")}`;
}
