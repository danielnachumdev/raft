import { useState } from "react";
import { toast } from "../../shared/chrome/toast";
import { temporaryOverrideSavedMessage } from "../../shared/gitops";
import {
  deleteAlertRule,
  dryRunAlertRule,
  exportAlertRules,
  importAlertRules,
  setAlertRuleEnabled,
  testAlertRule,
} from "./alertsApi";
import type { AlertRule } from "./alertsHelpers";
import { userFacingError } from "../../shared/userFacingError.ts";

type ImportDoc = { version: number; rules: AlertRule[] };

/** Per-rule async actions with a shared busy id and toast feedback. */
export function useAlertRuleActions(reload: () => Promise<void>) {
  const [busyId, setBusyId] = useState<string | null>(null);

  async function guarded(rule: AlertRule, fallback: string, run: () => Promise<void>) {
    setBusyId(rule.id);
    try {
      await run();
    } catch (err) {
      toast.bad(userFacingError(err, fallback));
    } finally {
      setBusyId(null);
    }
  }

  return {
    busyId,
    toggle: (rule: AlertRule) =>
      guarded(rule, "Toggle failed", async () => {
        await setAlertRuleEnabled(rule.id, !rule.enabled);
        toast.warning(temporaryOverrideSavedMessage("alerts.yaml"));
        await reload();
      }),
    remove: (rule: AlertRule) =>
      guarded(rule, "Delete failed", async () => {
        await deleteAlertRule(rule.id);
        toast.warning(temporaryOverrideSavedMessage("alerts.yaml"));
        await reload();
      }),
    dryRun: (rule: AlertRule) =>
      guarded(rule, "Dry run failed", async () => {
        const report = await dryRunAlertRule({ ruleId: rule.id });
        const matched = report.subjects.filter((s) => s.matched).length;
        toast.regular(
          `Dry run ${rule.id}: ${matched}/${report.subjects.length} matched`,
        );
      }),
    sendTest: (rule: AlertRule) =>
      guarded(rule, "Test failed", async () => {
        const result = await testAlertRule(rule.id);
        if (result.ok) toast.good("Test notification sent.");
        else toast.bad("Test notification failed.");
      }),
  };
}

export async function downloadAlertRules(): Promise<void> {
  try {
    const doc = await exportAlertRules();
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "raft-alerts.json";
    a.click();
    URL.revokeObjectURL(url);
    toast.good("Alert rules exported");
  } catch (err) {
    toast.bad(userFacingError(err, "Export failed"));
  }
}

/** Parse an export file; throws with an operator-readable message. */
export async function readImportFile(file: File): Promise<ImportDoc> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    throw new Error(`${file.name} is not valid JSON (use a file from Export).`);
  }
  const doc = parsed as Partial<ImportDoc> | null;
  if (!doc || !Array.isArray(doc.rules)) {
    throw new Error(`${file.name} has no "rules" list.`);
  }
  return { version: doc.version ?? 1, rules: doc.rules };
}

export async function applyImport(doc: ImportDoc, prune: boolean): Promise<void> {
  await importAlertRules(doc, prune);
  toast.warning(temporaryOverrideSavedMessage("alerts.yaml"));
}
