import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { StatusRow } from "../../src/shared/api/index.ts";
import { summarizeStatus } from "../../src/status/model/statusSummary.ts";

function row(name: string, status: string): StatusRow {
  return {
    service: name,
    name,
    role: "app",
    group: "-",
    status,
    cpu: "-",
    memory: "-",
    started: "-",
    uptime: "-",
    external_urls: [],
  };
}

describe("summarizeStatus", () => {
  it("buckets rows by status tone", () => {
    const summary = summarizeStatus([
      row("demo-api", "running"),
      row("demo-web", "running"),
      row("demo-worker", "exited"),
      row("demo-batch", "scaled-to-zero"),
      row("demo-cron", "starting"),
      row("demo-new", "created"),
    ]);
    assert.equal(summary.total, 6);
    assert.equal(summary.running, 2);
    assert.equal(summary.idle, 1);
    assert.equal(summary.attention, 2);
    assert.deepEqual(summary.attentionNames, ["demo-worker", "demo-cron"]);
  });

  it("handles an empty stack", () => {
    const summary = summarizeStatus([]);
    assert.equal(summary.total, 0);
    assert.deepEqual(summary.attentionNames, []);
  });
});
