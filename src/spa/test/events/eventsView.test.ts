import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  EVENT_KIND_GROUPS,
  eventTone,
  formatClock,
  formatFull,
  groupEventsByDay,
} from "../../src/events/eventsView.ts";

const row = (ts: string, kind = "deploy.apply") => ({ ts, kind, summary: kind });

describe("eventTone", () => {
  it("maps known kinds and defaults to neutral", () => {
    assert.equal(eventTone("alert.fired"), "bad");
    assert.equal(eventTone("alert.resolved"), "ok");
    assert.equal(eventTone("service.down"), "warn");
    assert.equal(eventTone("scale.wake"), "idle");
    assert.equal(eventTone("firewall.apply"), "neutral");
  });

  it("lists every toned kind in a filter group", () => {
    const listed = new Set(EVENT_KIND_GROUPS.flatMap((g) => g.kinds));
    for (const kind of ["alert.fired", "scale.idle_stop", "stack.purge"]) {
      assert.ok(listed.has(kind), kind);
    }
  });
});

describe("groupEventsByDay", () => {
  const now = new Date(2026, 9, 19, 15, 0, 0).getTime();

  it("buckets newest-first under Today / Yesterday / date", () => {
    const groups = groupEventsByDay(
      [
        row(new Date(2026, 9, 17, 9).toISOString()),
        row(new Date(2026, 9, 19, 8).toISOString()),
        row(new Date(2026, 9, 18, 22).toISOString()),
        row(new Date(2026, 9, 19, 14).toISOString(), "stack.purge"),
      ],
      now,
    );
    assert.deepEqual(
      groups.map((g) => [g.label === "Today" || g.label === "Yesterday" ? g.label : "date", g.rows.length]),
      [
        ["Today", 2],
        ["Yesterday", 1],
        ["date", 1],
      ],
    );
    assert.equal(groups[0].rows[0].kind, "stack.purge");
  });

  it("keeps unparseable timestamps in their own bucket", () => {
    const groups = groupEventsByDay([row("not-a-date")], now);
    assert.equal(groups[0].label, "Unknown date");
  });
});

describe("formatClock / formatFull", () => {
  it("pass through unparseable input", () => {
    assert.equal(formatClock("nope"), "nope");
    assert.equal(formatFull("nope"), "nope");
  });

  it("format parseable timestamps", () => {
    assert.match(formatClock("2026-10-19T12:34:56Z"), /\d{2}.\d{2}.\d{2}/);
    assert.ok(formatFull("2026-10-19T12:34:56Z").length > 0);
  });
});
