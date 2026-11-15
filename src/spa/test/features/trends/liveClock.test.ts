import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  liveClockRunning,
  livePollPlan,
} from "../../../src/features/trends/chart/liveClock.ts";

describe("liveClockRunning", () => {
  it("ticks only for rolling windows on screen", () => {
    assert.equal(liveClockRunning(true, true), true);
    assert.equal(liveClockRunning(true, false), false);
    assert.equal(liveClockRunning(false, true), false);
    assert.equal(liveClockRunning(false, false), false);
  });
});

describe("livePollPlan", () => {
  const idle = { busy: false, live: true, visible: true, resumed: false };

  it("polls on the interval when live, idle and visible", () => {
    assert.deepEqual(livePollPlan(idle), { run: true, pollNow: false });
  });

  it("pauses while off-screen, busy or fixed-range", () => {
    for (const patch of [{ visible: false }, { busy: true }, { live: false }]) {
      assert.deepEqual(
        livePollPlan({ ...idle, ...patch, resumed: true }),
        { run: false, pollNow: false },
      );
    }
  });

  it("polls immediately when scrolling back in", () => {
    assert.deepEqual(
      livePollPlan({ ...idle, resumed: true }),
      { run: true, pollNow: true },
    );
  });
});
