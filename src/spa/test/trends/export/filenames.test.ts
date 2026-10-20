import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { graphExportBasename } from "../../../src/trends/export/filenames.ts";

describe("graphExportBasename", () => {
  it("slugs titles without hostnames or spaces", () => {
    assert.equal(graphExportBasename("CPU"), "raft-trends-cpu");
    assert.equal(
      graphExportBasename("Request rate"),
      "raft-trends-request-rate",
    );
    assert.equal(graphExportBasename("  "), "raft-trends-graph");
  });
});
