import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { YamlHighlighter } from "../../src/settings/YamlHighlighter.ts";

describe("service definition YAML display", () => {
  it("highlights applied App manifest keys for Definition panel", () => {
    const yaml = [
      "apiVersion: raft/v1",
      "kind: App",
      "metadata:",
      "  name: demo-api",
      "spec:",
      "  publicHost: demo-api.test",
      "  tls: off",
    ].join("\n");
    const html = new YamlHighlighter().highlightHtml(yaml);
    assert.match(html, /class="yh-key">apiVersion</);
    assert.match(html, /class="yh-key">name</);
    assert.match(html, /demo-api/);
  });
});
