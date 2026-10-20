import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { graphExportItems } from "../../../src/trends/dashboard/ui/graphExportItems.ts";

describe("graphExportItems", () => {
  it("lists CSV only when PNG capture is unavailable", () => {
    const items = graphExportItems({ onCsv: () => undefined });
    assert.deepEqual(
      items.map((i) => i.id),
      ["csv"],
    );
    assert.equal(items[0]?.label, "CSV");
  });

  it("lists CSV and PNG when capture is available", () => {
    const items = graphExportItems({
      onCsv: () => undefined,
      onPng: () => undefined,
    });
    assert.deepEqual(
      items.map((i) => i.id),
      ["csv", "png"],
    );
    assert.equal(items[1]?.label, "PNG");
  });

  it("disables PNG and shows busy label while exporting", () => {
    const items = graphExportItems({
      onCsv: () => undefined,
      onPng: () => undefined,
      pngBusy: true,
    });
    const png = items.find((i) => i.id === "png");
    assert.equal(png?.label, "Exporting…");
    assert.equal(png?.disabled, true);
  });
});
