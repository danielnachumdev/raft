import { toast } from "../../chrome/toast/index.ts";
import type { MetricsSeries } from "../../shared/api/index.ts";
import {
  graphTitle,
  graphView,
  type TrendsGraphDraft,
} from "../dashboard/model/index.ts";
import type { DashboardMetrics } from "../dashboard/ui/useDashboardMetrics.ts";
import {
  captureElementPng,
  dataUrlToBlob,
  type CapturePngOptions,
} from "./capturePng.ts";
import { downloadBlob, downloadTextFile } from "./downloadFile.ts";
import { graphExportBasename } from "./filenames.ts";
import { encodeMetricsCsv } from "./metricsCsv.ts";

/** Series + CSV text for one graph (visible series only). */
export function graphCsvPayload(
  config: TrendsGraphDraft,
  data: Pick<DashboardMetrics, "series" | "available">,
): { title: string; series: MetricsSeries[]; csv: string } {
  const view = graphView(config, {
    series: data.series,
    available: data.available,
  });
  const extraPointKeys = view.metrics.map((m) => m.id);
  const csv = encodeMetricsCsv(view.visible, { extraPointKeys });
  return { title: view.title || graphTitle(config), series: view.visible, csv };
}

/** Download CSV scoped to the graph's visible series. */
export function exportGraphCsv(
  config: TrendsGraphDraft,
  data: Pick<DashboardMetrics, "series" | "available">,
): void {
  const { title, csv } = graphCsvPayload(config, data);
  const name = `${graphExportBasename(title)}.csv`;
  downloadTextFile(csv, name, "text/csv;charset=utf-8");
  toast.good(`Exported ${name}`);
}

/** High-res PNG of the expanded graph node. */
export async function exportGraphPng(
  node: HTMLElement | null,
  title: string,
  opts: CapturePngOptions = {},
): Promise<void> {
  if (!node) {
    toast.bad("Graph is not ready to export");
    return;
  }
  try {
    const dataUrl = await captureElementPng(node, opts);
    const blob = await dataUrlToBlob(dataUrl);
    const name = `${graphExportBasename(title)}.png`;
    downloadBlob(blob, name);
    toast.good(`Exported ${name}`);
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : "PNG export failed");
  }
}
