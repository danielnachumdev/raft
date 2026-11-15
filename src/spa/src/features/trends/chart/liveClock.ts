/**
 * Rolling chart clocks only tick for live windows that are on screen;
 * off-screen charts catch up with one immediate tick when they scroll back in.
 */
export function liveClockRunning(rolling: boolean, visible: boolean): boolean {
  return rolling && visible;
}

/**
 * Live metric polls pause while charts are off-screen. Resuming polls once
 * right away (``since`` cursor) instead of waiting a full interval.
 */
export function livePollPlan(args: {
  busy: boolean;
  live: boolean;
  visible: boolean;
  resumed: boolean;
}): { run: boolean; pollNow: boolean } {
  const run = !args.busy && args.live && args.visible;
  return { run, pollNow: run && args.resumed };
}
