import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { MetricsSeries } from "../../../src/shared/api/index.ts";
import {
  columnsForExport,
  encodeMetricsCsv,
  escapeCsv,
  SERVER_METRICS_CSV_COLUMNS,
} from "../../../src/trends/export/metricsCsv.ts";
import { graphCsvPayload } from "../../../src/trends/export/graphExport.ts";
import type { TrendsGraphDraft } from "../../../src/trends/dashboard/model/types.ts";

const site: MetricsSeries = {
  id: "demo-api",
  label: "demo-api",
  kind: "container",
  role: "app",
  group: "demo",
  points: [
    {
      t: "2026-01-01T00:00:00+00:00",
      cpu_percent: 1.5,
      memory_used_percent: 10,
      rps: 42,
    },
  ],
};

const other: MetricsSeries = {
  id: "raft-gate",
  label: "raft-gate",
  kind: "container",
  role: "gate",
  group: null,
  points: [
    {
      t: "2026-01-01T00:00:00+00:00",
      cpu_percent: 0.2,
      rps: 1,
    },
  ],
};

describe("encodeMetricsCsv", () => {
  it("matches the server resource header when no extras", () => {
    const text = encodeMetricsCsv([site]);
    const header = text.split("\n", 1)[0] ?? "";
    assert.equal(header, SERVER_METRICS_CSV_COLUMNS.join(","));
    assert.match(text, /demo-api,demo-api,container,app,demo,1.5,10/);
  });

  it("appends HTTP metric columns after the server dialect", () => {
    const text = encodeMetricsCsv([site], { extraPointKeys: ["rps"] });
    const header = text.split("\n", 1)[0] ?? "";
    assert.ok(header.startsWith(SERVER_METRICS_CSV_COLUMNS.join(",")));
    assert.ok(header.endsWith(",rps"));
    assert.match(text, /,42\n/);
  });

  it("scopes rows to the series list passed in", () => {
    const text = encodeMetricsCsv([site]);
    assert.ok(text.includes("demo-api"));
    assert.equal(text.includes("raft-gate"), false);
  });

  it("escapes commas and quotes in cells", () => {
    assert.equal(escapeCsv('a,b'), '"a,b"');
    assert.equal(escapeCsv('say "hi"'), '"say ""hi"""');
  });
});

describe("columnsForExport", () => {
  it("dedupes extras and skips resource keys already in the dialect", () => {
    assert.deepEqual(columnsForExport(["rps", "rps", "cpu_percent"]), [
      ...SERVER_METRICS_CSV_COLUMNS,
      "rps",
    ]);
  });
});

describe("graphCsvPayload", () => {
  it("exports only the graph's visible series and metric extras", () => {
    const draft: TrendsGraphDraft = {
      title: "CPU",
      metricIds: ["cpu_percent"],
      viewMode: "per_service",
      selected: ["demo-api"],
      size: "half",
    };
    const available = [
      {
        id: "demo-api",
        label: "demo-api",
        kind: "container",
        role: "app",
        group: "demo",
      },
      {
        id: "raft-gate",
        label: "raft-gate",
        kind: "container",
        role: "gate",
        group: null,
      },
    ];
    const { series, csv, title } = graphCsvPayload(draft, {
      series: [site, other],
      available,
    });
    assert.equal(title, "CPU");
    assert.deepEqual(
      series.map((s) => s.id),
      ["demo-api"],
    );
    assert.ok(csv.includes("demo-api"));
    assert.equal(csv.includes("raft-gate"), false);
    assert.equal(csv.split("\n", 1)[0], SERVER_METRICS_CSV_COLUMNS.join(","));
  });

  it("adds rps column for an HTTP graph", () => {
    const draft: TrendsGraphDraft = {
      title: "Request rate",
      metricIds: ["rps"],
      viewMode: "per_service",
      selected: null,
      size: "half",
    };
    const available = [
      {
        id: "demo-api",
        label: "demo-api",
        kind: "container",
        role: "app",
        group: "demo",
      },
    ];
    const { csv } = graphCsvPayload(draft, {
      series: [site],
      available,
    });
    assert.ok((csv.split("\n", 1)[0] ?? "").endsWith(",rps"));
    assert.match(csv, /,42\n/);
  });
});
