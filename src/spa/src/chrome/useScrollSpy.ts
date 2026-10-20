import { useEffect, useState } from "react";
import { activeSectionId } from "./scrollSpy";

const SPY_OFFSET_PX = 140;

/** Track which of ``ids`` is the current reading position. */
export function useScrollSpy(ids: string[]): string | null {
  const key = ids.join(",");
  const [active, setActive] = useState<string | null>(ids[0] ?? null);
  useEffect(() => {
    const update = () => {
      const tops = key
        .split(",")
        .map((id) => document.getElementById(id))
        .filter((el): el is HTMLElement => el !== null)
        .map((el) => ({ id: el.id, top: el.getBoundingClientRect().top }));
      const root = document.documentElement;
      const atBottom = window.innerHeight + window.scrollY >= root.scrollHeight - 2;
      setActive(activeSectionId(tops, SPY_OFFSET_PX, atBottom));
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [key]);
  return active;
}
