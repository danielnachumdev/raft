import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import { DASHBOARD_DOCUMENT_TITLE } from "../../src/shared/api/status.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");

describe("dashboard document title", () => {
  it("is always exactly raft dashboard", () => {
    assert.equal(DASHBOARD_DOCUMENT_TITLE, "raft dashboard");
  });

  it("hardcodes the title in index.html and status/service pages", () => {
    const index = readFileSync(join(root, "index.html"), "utf8");
    const dashboard = readFileSync(
      join(root, "src/shell/Dashboard.tsx"),
      "utf8",
    );
    const service = readFileSync(
      join(root, "src/service/ServicePage.tsx"),
      "utf8",
    );
    const statusApi = readFileSync(
      join(root, "src/shared/api/status.ts"),
      "utf8",
    );
    assert.match(index, /<title>raft dashboard<\/title>/);
    assert.match(dashboard, /DASHBOARD_DOCUMENT_TITLE/);
    assert.doesNotMatch(dashboard, /Host <code>/);
    assert.match(service, /DASHBOARD_DOCUMENT_TITLE/);
    assert.doesNotMatch(service, /raft - \$\{/);
    assert.doesNotMatch(statusApi, /documentTitleForHost/);
  });
});
