/** Extra margin around the viewport so charts wake just before scrolling in. */
export const VIEWPORT_ROOT_MARGIN = "200px";

/**
 * Whether an observed element counts as on-screen. Unobserved elements and
 * environments without IntersectionObserver (tests, old browsers) stay visible
 * so nothing silently stops updating.
 */
export function viewportVisible(args: {
  observed: boolean;
  supported: boolean;
  intersecting: boolean;
}): boolean {
  if (!args.observed || !args.supported) return true;
  return args.intersecting;
}

export function intersectionObserverSupported(): boolean {
  return typeof IntersectionObserver !== "undefined";
}
