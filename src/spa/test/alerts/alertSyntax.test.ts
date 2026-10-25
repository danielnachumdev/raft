import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  alertDocumentJson,
  alertDocumentYaml,
} from "../../src/alerts/alertDocumentYaml.ts";
import {
  ALERT_EXAMPLES_GITHUB_URL,
  ALERT_SYNTAX_EXAMPLE,
} from "../../src/alerts/alertSyntaxExamples.ts";

describe("alert syntax guide helpers", () => {
  it("dumps the demo document as YAML with rule ids", () => {
    const yaml = alertDocumentYaml(ALERT_SYNTAX_EXAMPLE);
    assert.match(yaml, /^version: 1$/m);
    assert.match(yaml, /id: demo-api-5xx-rate/);
    assert.match(yaml, /signal: metrics\.http/);
    assert.match(yaml, /target: demo-api/);
    assert.doesNotMatch(yaml, /ops@|192\.168\.|token/i);
  });

  it("dumps the demo document as pretty JSON", () => {
    const json = alertDocumentJson(ALERT_SYNTAX_EXAMPLE);
    const parsed = JSON.parse(json) as typeof ALERT_SYNTAX_EXAMPLE;
    assert.equal(parsed.version, 1);
    assert.equal(parsed.rules[0]?.id, "demo-api-5xx-rate");
    assert.equal(parsed.rules[1]?.condition.signal, "control.container_status");
  });

  it("points at the checked-in examples tree", () => {
    assert.match(ALERT_EXAMPLES_GITHUB_URL, /examples\/alerts$/);
  });
});
