import { useEffect, useState } from "react";
import {
  intersectionObserverSupported,
  VIEWPORT_ROOT_MARGIN,
  viewportVisible,
} from "./viewportVisibility";

/**
 * Callback ref + "is it near the viewport" flag. Used to pause cosmetic
 * periodic work (rolling chart clocks, live polls) while scrolled away.
 */
export function useInViewport<T extends Element>(
  rootMargin: string = VIEWPORT_ROOT_MARGIN,
): [(el: T | null) => void, boolean] {
  const [el, setEl] = useState<T | null>(null);
  const [intersecting, setIntersecting] = useState(true);
  const supported = intersectionObserverSupported();
  useEffect(() => {
    if (!el || !supported) return;
    const io = new IntersectionObserver(
      (entries) => {
        const last = entries[entries.length - 1];
        if (last) setIntersecting(last.isIntersecting);
      },
      { rootMargin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [el, rootMargin, supported]);
  return [
    setEl,
    viewportVisible({ observed: el !== null, supported, intersecting }),
  ];
}
