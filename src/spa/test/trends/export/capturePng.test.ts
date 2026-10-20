import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  captureElementPng,
  GRAPH_PNG_PIXEL_RATIO,
} from "../../../src/trends/export/capturePng.ts";

describe("captureElementPng", () => {
  it("uses the injectable capture at the default high DPI ratio", async () => {
    const seen: { ratio: number } = { ratio: 0 };
    const node = { tagName: "ARTICLE" } as HTMLElement;
    const dataUrl = await captureElementPng(node, {
      capture: async (_el, pixelRatio) => {
        seen.ratio = pixelRatio;
        return "data:image/png;base64,AAA";
      },
    });
    assert.equal(seen.ratio, GRAPH_PNG_PIXEL_RATIO);
    assert.equal(dataUrl, "data:image/png;base64,AAA");
  });

  it("honors an explicit pixelRatio", async () => {
    let ratio = 0;
    await captureElementPng({} as HTMLElement, {
      pixelRatio: 2,
      capture: async (_el, pixelRatio) => {
        ratio = pixelRatio;
        return "data:image/png;base64,BBB";
      },
    });
    assert.equal(ratio, 2);
  });
});
