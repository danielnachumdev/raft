import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { YamlHighlighter } from "../../src/settings/YamlHighlighter.ts";

const yh = new YamlHighlighter();

describe("YamlHighlighter", () => {
  it("highlights keys, scalars, and comments", () => {
    const html = yh.highlightHtml(
      [
        "# demo host settings",
        "logging:",
        "  level: info  # host log",
        "edge:",
        '  publicHost: "ops.example.com"',
        "  enabled: true",
        "  port: 443",
        "  empty: null",
        "  - demo-api",
      ].join("\n"),
    );
    assert.match(html, /class="yh-comment"># demo host settings</);
    assert.match(html, /class="yh-key">logging</);
    assert.match(html, /class="yh-key">level</);
    assert.match(html, /class="yh-string">info</);
    assert.match(html, /class="yh-comment"># host log</);
    assert.match(html, /class="yh-string">&quot;ops\.example\.com&quot;</);
    assert.match(html, /class="yh-bool">true</);
    assert.match(html, /class="yh-number">443</);
    assert.match(html, /class="yh-null">null</);
    assert.match(html, /class="yh-punct">- /);
    assert.match(html, /class="yh-string">demo-api</);
  });

  it("escapes HTML in source text", () => {
    const html = yh.highlightHtml('note: "<script>&"</script>"');
    assert.equal(html.includes("<script>"), false);
    assert.match(html, /&lt;script&gt;/);
    assert.match(html, /&amp;/);
  });

  it("round-trips token text to the original source", () => {
    const source = "a: 1\n# c\nb: 'x'\n";
    assert.equal(
      yh.tokenize(source).map((t) => t.text).join(""),
      source,
    );
  });
});
