import { useEffect } from "react";

/** Scroll to ``#hash`` once async content that owns the anchor has rendered. */
export function useHashScroll(hash: string, ready: boolean): void {
  useEffect(() => {
    if (!ready || !hash) return;
    const el = document.getElementById(decodeURIComponent(hash.slice(1)));
    el?.scrollIntoView({ block: "start" });
  }, [hash, ready]);
}
