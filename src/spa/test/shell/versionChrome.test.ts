import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import { versionChromeText } from "../../src/shared/api/status.ts";

const shellRoot = join(dirname(fileURLToPath(import.meta.url)), "../../src/shell");

describe("versionChromeText", () => {
  it("prefers label over packaging semver", () => {
    assert.equal(
      versionChromeText({
        package: "0.1.0",
        line: "raft 0.1.0 (git main@abc1234)",
        label: "main@abc1234",
      }),
      "main@abc1234",
    );
  });

  it("falls back to package when label missing", () => {
    assert.equal(
      versionChromeText({ package: "0.12.7", line: "raft 0.12.7" }),
      "0.12.7",
    );
  });
});

describe("AppShell version chrome", () => {
  it("renders versionChromeText for the top-bar badge", () => {
    const src = readFileSync(join(shellRoot, "AppShell.tsx"), "utf8");
    assert.match(src, /versionChromeText/);
    assert.match(src, /raft-version/);
  });
});
