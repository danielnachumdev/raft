/** Dashboard health roll-up across control plane + apps. */

import type { StatusRow } from "../../shared/api/index.ts";
import { statusTone } from "./statusTone.ts";

export type StatusSummary = {
  total: number;
  running: number;
  attention: number;
  idle: number;
  /** Display names of rows needing attention (bad / warn tones). */
  attentionNames: string[];
};

export function summarizeStatus(rows: StatusRow[]): StatusSummary {
  const summary: StatusSummary = {
    total: rows.length,
    running: 0,
    attention: 0,
    idle: 0,
    attentionNames: [],
  };
  for (const row of rows) {
    const tone = statusTone(row.status);
    if (tone === "ok") summary.running += 1;
    if (tone === "idle") summary.idle += 1;
    if (tone === "bad" || tone === "warn") {
      summary.attention += 1;
      summary.attentionNames.push(row.name);
    }
  }
  return summary;
}
