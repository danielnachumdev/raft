import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  addLeaf,
  countLeaves,
  defaultLeaf,
  emptyRuleDraft,
  formatAlertDuration,
  kindsForSource,
  parseAlertDuration,
  relativeTime,
  routingLabel,
  ruleStateFor,
  summarizeCondition,
  validateDraft,
  wrapInGroup,
  type AlertCatalogPayload,
} from "../../src/alerts/alertsHelpers.ts";

const catalog: AlertCatalogPayload = {
  sources: [
    {
      type_id: "metrics.http",
      label: "HTTP",
      value_type: "numeric",
      select_fields: [
        {
          key: "target",
          label: "Target",
          kind: "select",
          options: [{ value: "demo-api", label: "demo-api" }],
          default: "demo-api",
        },
        {
          key: "metric",
          label: "Metric",
          kind: "select",
          options: [{ value: "error_rate_5xx", label: "5xx" }],
          default: "error_rate_5xx",
        },
      ],
      metrics: [],
    },
  ],
  kinds: [
    {
      kind_id: "threshold",
      label: "Threshold",
      value_types: ["numeric"],
      fields: [{ key: "value", label: "Value", kind: "number", default: 0.05 }],
    },
  ],
  severities: ["info", "warning", "error", "critical"],
  noData: ["ok", "alerting", "keep"],
  limits: { maxRules: 200, maxLeaves: 8, maxDepth: 3 },
};

describe("alertsHelpers", () => {
  it("parses and formats durations", () => {
    assert.equal(parseAlertDuration("5m"), 300);
    assert.equal(parseAlertDuration("300"), 300);
    assert.equal(parseAlertDuration("nope"), null);
    assert.equal(formatAlertDuration(300), "5m");
    assert.equal(formatAlertDuration(45), "45s");
  });

  it("builds drafts and validates", () => {
    const draft = emptyRuleDraft(catalog);
    draft.id = "demo-api-5xx-rate";
    draft.name = "demo";
    assert.deepEqual(validateDraft(draft), []);
    draft.id = "BAD";
    assert.ok(validateDraft(draft).length > 0);
  });

  it("summarizes and edits trees", () => {
    const leaf = defaultLeaf(catalog);
    assert.ok(summarizeCondition(leaf).includes("metrics.http"));
    const group = wrapInGroup(leaf, [], "all");
    assert.equal(countLeaves(group), 1);
    const grown = addLeaf(group, [], defaultLeaf(catalog));
    assert.equal(countLeaves(grown), 2);
  });

  it("routing and state helpers", () => {
    assert.equal(routingLabel([], []), "All enabled channels");
    assert.equal(
      routingLabel(["ops-primary", "gone"], [{ id: "ops-primary" }]),
      "ops-primary, gone (missing)",
    );
    assert.equal(ruleStateFor(null, "x", false), "disabled");
    assert.equal(
      ruleStateFor({ rules: { x: { state: "firing" } } }, "x", true),
      "firing",
    );
    assert.ok(kindsForSource(catalog, "metrics.http").length >= 1);
    assert.ok(relativeTime(new Date().toISOString(), Date.now()).includes("ago"));
  });
});
