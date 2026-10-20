import { toPng } from "html-to-image";

/** Default scale for crisp expanded-graph captures (CSS px × ratio). */
export const GRAPH_PNG_PIXEL_RATIO = 3;

export type CapturePngOptions = {
  pixelRatio?: number;
  /** Injectable for tests. */
  capture?: (node: HTMLElement, pixelRatio: number) => Promise<string>;
};

/**
 * High-DPI PNG data URL of a DOM node (expanded Trends graph).
 * Uses ``html-to-image`` so Recharts SVG + chrome rasterize together.
 */
export async function captureElementPng(
  node: HTMLElement,
  opts: CapturePngOptions = {},
): Promise<string> {
  const pixelRatio = opts.pixelRatio ?? GRAPH_PNG_PIXEL_RATIO;
  const capture = opts.capture ?? defaultCapture;
  return capture(node, pixelRatio);
}

async function defaultCapture(
  node: HTMLElement,
  pixelRatio: number,
): Promise<string> {
  return toPng(node, {
    pixelRatio,
    cacheBust: true,
    // Keep chart background readable when pasted into docs/slides.
    backgroundColor: readBackground(node),
  });
}

function readBackground(node: HTMLElement): string {
  const fromCss = getComputedStyle(node).backgroundColor;
  if (fromCss && fromCss !== "rgba(0, 0, 0, 0)" && fromCss !== "transparent") {
    return fromCss;
  }
  return "#ffffff";
}

/** Turn a data URL into a Blob for ``downloadBlob``. */
export async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  const res = await fetch(dataUrl);
  return res.blob();
}
