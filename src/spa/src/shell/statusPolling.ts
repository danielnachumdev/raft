import { STATUS_POLL_MS } from "../shared/api/index.ts";

/** Interval poll while visible; refetch once when the tab becomes visible again. */
export function bindStatusPolling(
  onTick: () => void,
  onLiveChange: (live: boolean) => void,
): () => void {
  let timer: number | undefined;

  const clear = () => {
    if (timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
  };

  const arm = () => {
    clear();
    if (!tabIsVisible()) {
      onLiveChange(false);
      return;
    }
    timer = window.setInterval(onTick, STATUS_POLL_MS);
    onLiveChange(true);
  };

  const onVisibility = () => {
    if (tabIsVisible()) {
      onTick();
      arm();
      return;
    }
    clear();
    onLiveChange(false);
  };

  arm();
  document.addEventListener("visibilitychange", onVisibility);
  return () => {
    clear();
    document.removeEventListener("visibilitychange", onVisibility);
  };
}

export function tabIsVisible(): boolean {
  return document.visibilityState === "visible";
}
