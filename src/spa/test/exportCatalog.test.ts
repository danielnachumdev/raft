import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildDownloadItems, type ExportOption } from "../src/export/items.ts";
import { logsDownloadUrl, metricsDownloadUrl } from "../src/export/urls.ts";

const logs: ExportOption[] = [
  {
    id: "txt",
    label: "Plain text",
    media_type: "text/plain; charset=utf-8",
    suffix: "txt",
  },
  {
    id: "json",
    label: "JSON",
    media_type: "application/json",
    suffix: "json",
  },
];

describe("buildDownloadItems", () => {
  it("maps catalog order into hrefs without hardcoding format ids", () => {
    const items = buildDownloadItems(logs, (id) => `/x?format=${id}`);
    assert.deepEqual(
      items.map((item) => item.id),
      ["txt", "json"],
    );
    assert.equal(items[0]?.href, "/x?format=txt");
    assert.equal(items[1]?.label, "JSON");
  });

  it("includes a newly registered format without caller changes", () => {
    const extra: ExportOption = {
      id: "tsv",
      label: "TSV",
      media_type: "text/tab-separated-values",
      suffix: "tsv",
    };
    const items = buildDownloadItems([...logs, extra], (id) => id);
    assert.equal(items[items.length - 1]?.id, "tsv");
  });
});

describe("download urls", () => {
  it("builds logs and metrics query strings from format id", () => {
    assert.equal(
      logsDownloadUrl("site", "json", 200),
      "/api/service/site/logs/download?format=json&tail=200",
    );
    assert.equal(
      metricsDownloadUrl({
        formatId: "csv",
        window: 3600,
        services: ["raft-gate", "site"],
      }),
      "/api/metrics/download?format=csv&window=3600&services=raft-gate%2Csite",
    );
  });
});
