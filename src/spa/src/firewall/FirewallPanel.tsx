import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { SaveBar } from "../chrome/SaveBar";
import { EmptyState } from "../chrome/StateViews";
import { toast } from "../chrome/toast";
import { useUnsavedGuard } from "../chrome/useUnsavedGuard";
import type {
  FirewallDocument,
  FirewallRecommendation,
  FirewallRule,
  FirewallServiceOption,
} from "./firewallApi";
import { IconPlus } from "./FirewallIcons";
import { FirewallImportModal } from "./FirewallImportModal";
import { FirewallRecommendations } from "./FirewallRecommendations";
import {
  FirewallRuleFormModal,
  type FirewallRuleFormSubmit,
} from "./FirewallRuleFormModal";
import { FirewallRuleTable } from "./FirewallRuleTable";
import "./FirewallPanel.css";

type Props = {
  document: FirewallDocument;
  services: FirewallServiceOption[];
  recommendations: FirewallRecommendation[];
  busy: boolean;
  /** Page header slot; receives the page-level actions (add/import/export/save). */
  header: (actions: ReactNode) => ReactNode;
  onSave: (doc: Pick<FirewallDocument, "version" | "rules">) => Promise<void>;
  onExport: () => Promise<FirewallDocument>;
  onImport: (body: unknown) => Promise<void>;
  onDismissRecommendation: (id: string) => Promise<void>;
};

/** Ordered firewall editor: header actions, recommendations, rule table, save bar. */
export function FirewallPanel(props: Props) {
  const [rules, setRules] = useState<FirewallRule[]>(props.document.rules);
  const [saved, setSaved] = useState<FirewallRule[]>(props.document.rules);
  const [editing, setEditing] = useState<FirewallRule | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<FirewallRule | null>(null);
  const [saving, setSaving] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  useEffect(() => {
    setRules(props.document.rules);
    setSaved(props.document.rules);
  }, [props.document]);

  const dirty = useMemo(
    () => JSON.stringify(rules) !== JSON.stringify(saved),
    [rules, saved],
  );
  const locked = props.busy || saving;
  useUnsavedGuard(dirty);

  async function persist() {
    setSaving(true);
    try {
      await props.onSave({ version: props.document.version || 1, rules });
      setSaved(rules);
      toast.good("Firewall applied (gate nginx reload)");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Failed to save firewall");
    } finally {
      setSaving(false);
    }
  }

  function onFormSubmit(body: FirewallRuleFormSubmit) {
    setRules(
      editing
        ? rules.map((r) => (r.id === body.id ? body : r))
        : [...rules.filter((r) => r.id !== body.id), body],
    );
    setFormOpen(false);
    setEditing(null);
  }

  function reorder(from: number, to: number) {
    if (to < 0 || to >= rules.length) return;
    const next = [...rules];
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row);
    setRules(next);
  }

  function applyRecommendation(item: FirewallRecommendation) {
    if (rules.some((r) => r.id === item.rule.id)) {
      toast.bad(`Rule id ${item.rule.id} already exists`);
      return;
    }
    setRules(item.append ? [...rules, item.rule] : [item.rule, ...rules]);
    toast.good("Recommendation added — Save to apply");
  }

  async function onExportClick() {
    try {
      downloadJson(await props.onExport(), "raft-firewall.json");
      toast.good("Firewall exported");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Export failed");
    }
  }

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const actions = (
    <>
      <button type="button" className="btn" id="firewall-import" disabled={locked} onClick={() => setImportOpen(true)}>
        Import
      </button>
      <button type="button" className="btn" id="firewall-export" disabled={locked} onClick={() => void onExportClick()}>
        Export
      </button>
      <button type="button" className="btn" id="firewall-add" disabled={locked} onClick={openCreate}>
        <IconPlus />
        Add rule
      </button>
      <button
        type="button"
        className={saving ? "btn btn-primary is-loading" : "btn btn-primary"}
        id="firewall-save"
        disabled={locked || !dirty}
        aria-busy={saving}
        onClick={() => void persist()}
      >
        {saving ? <span className="spinner btn-spinner" aria-hidden="true" /> : null}
        Save &amp; apply
      </button>
    </>
  );

  return (
    <>
      {props.header(actions)}

      <FirewallRecommendations
        items={props.recommendations}
        busy={locked}
        onApply={applyRecommendation}
        onDismiss={props.onDismissRecommendation}
      />

      <section className="panel fw-panel" id="firewall-panel">
        <div className="panel-head">
          <h2>
            Rules
            {rules.length ? <span className="panel-count">{rules.length}</span> : null}
          </h2>
        </div>
        <p className="panel-lede">
          First match wins, top to bottom. Drag the grip or use the arrows to
          reorder.
        </p>
        {rules.length === 0 ? (
          <EmptyState
            id="firewall-empty"
            title="No firewall rules."
            action={
              <button type="button" className="btn btn-sm" disabled={locked} onClick={openCreate}>
                <IconPlus />
                Add rule
              </button>
            }
          >
            Apply a recommendation, add a rule, or import an export — then Save
            &amp; apply.
          </EmptyState>
        ) : (
          <FirewallRuleTable
            rules={rules}
            locked={locked}
            onReorder={reorder}
            onEdit={(rule) => {
              setEditing(rule);
              setFormOpen(true);
            }}
            onRemove={setPendingDelete}
          />
        )}
      </section>

      <SaveBar
        open={dirty}
        id="firewall-dirty"
        message="Unsaved firewall changes — not live until you Save & apply."
        saveLabel="Save & apply"
        saving={saving}
        disabled={props.busy}
        onSave={() => void persist()}
        onDiscard={() => setRules(saved)}
      />

      <FirewallRuleFormModal
        open={formOpen}
        mode={editing ? "edit" : "create"}
        rule={editing}
        services={props.services}
        busy={false}
        onClose={() => setFormOpen(false)}
        onSubmit={onFormSubmit}
      />

      <ConfirmPopup
        open={pendingDelete !== null}
        title="Remove rule?"
        message={
          pendingDelete
            ? `Remove ${pendingDelete.id} (${pendingDelete.cidr}) from the table?`
            : ""
        }
        confirmLabel="Remove"
        danger
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          const id = pendingDelete?.id;
          setPendingDelete(null);
          setRules(rules.filter((r) => r.id !== id));
        }}
      />

      <FirewallImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImport={props.onImport}
      />
    </>
  );
}

function downloadJson(doc: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(doc, null, 2) + "\n"], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
