import {
  useEffect,
  useMemo,
  useState,
  type DragEvent,
  type ReactNode,
} from "react";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { Modal } from "../chrome/Modal";
import { toast } from "../chrome/toast";
import type {
  FirewallDocument,
  FirewallRecommendation,
  FirewallRule,
  FirewallServiceOption,
} from "./firewallApi";
import { formatFirewallPort } from "./firewallApi";
import {
  IconChevronDown,
  IconChevronUp,
  IconGrip,
  IconPencil,
  IconPlus,
  IconTrash,
} from "./FirewallIcons";
import { FirewallRecommendations } from "./FirewallRecommendations";
import {
  FirewallRuleFormModal,
  type FirewallRuleFormSubmit,
} from "./FirewallRuleFormModal";
import "./FirewallPanel.css";

type Props = {
  document: FirewallDocument;
  services: FirewallServiceOption[];
  recommendations: FirewallRecommendation[];
  busy: boolean;
  onSave: (doc: Pick<FirewallDocument, "version" | "rules">) => Promise<void>;
  onExport: () => Promise<FirewallDocument>;
  onImport: (body: unknown) => Promise<void>;
  onDismissRecommendation: (id: string) => Promise<void>;
};

/** Ordered firewall table with icon actions, drag reorder, recommendations. */
export function FirewallPanel(props: Props) {
  const [rules, setRules] = useState<FirewallRule[]>(props.document.rules);
  const [saved, setSaved] = useState<FirewallRule[]>(props.document.rules);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [editing, setEditing] = useState<FirewallRule | null>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<FirewallRule | null>(null);
  const [saving, setSaving] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

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

  async function persist(next: FirewallRule[]) {
    setSaving(true);
    try {
      await props.onSave({ version: props.document.version || 1, rules: next });
      setRules(next);
      setSaved(next);
      toast.good("Firewall applied (gate nginx reload)");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Failed to save firewall");
    } finally {
      setSaving(false);
    }
  }

  function onFormSubmit(body: FirewallRuleFormSubmit) {
    setFormBusy(true);
    try {
      const next =
        formMode === "create"
          ? [...rules.filter((r) => r.id !== body.id), body]
          : rules.map((r) => (r.id === body.id ? body : r));
      setRules(next);
      setFormOpen(false);
      setEditing(null);
    } finally {
      setFormBusy(false);
    }
  }

  function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= rules.length) return;
    const next = [...rules];
    const [row] = next.splice(index, 1);
    next.splice(target, 0, row);
    setRules(next);
  }

  function onDrop(target: number) {
    if (dragIndex === null || dragIndex === target) return;
    const next = [...rules];
    const [row] = next.splice(dragIndex, 1);
    next.splice(target, 0, row);
    setRules(next);
    setDragIndex(null);
  }

  function applyRecommendation(item: FirewallRecommendation) {
    if (rules.some((r) => r.id === item.rule.id)) {
      toast.bad(`Rule id ${item.rule.id} already exists`);
      return;
    }
    setRules(
      item.append ? [...rules, item.rule] : [item.rule, ...rules],
    );
    toast.good("Recommendation added — Save to apply");
  }

  async function onExportClick() {
    try {
      const doc = await props.onExport();
      const blob = new Blob([JSON.stringify(doc, null, 2) + "\n"], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "raft-firewall.json";
      a.click();
      URL.revokeObjectURL(url);
      toast.good("Firewall exported");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Export failed");
    }
  }

  async function onImportConfirm() {
    setImportBusy(true);
    try {
      const parsed = JSON.parse(importText) as unknown;
      await props.onImport(parsed);
      setImportOpen(false);
      setImportText("");
      toast.good("Firewall imported (gate nginx reload)");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImportBusy(false);
    }
  }

  return (
    <section className="panel fw-panel" id="firewall-panel">
      <div className="fw-panel-head">
        <div>
          <h2>Firewall rules</h2>
          <p className="muted">
            First match wins. Drag the grip or use the arrows to reorder.
            {props.document.source === "acl-v1-migrated"
              ? " Showing migrated ACL v1 rules until you Save."
              : null}
          </p>
          {dirty ? (
            <p className="fw-dirty" id="firewall-dirty" role="status">
              Unsaved changes — not live until you Save &amp; apply.
            </p>
          ) : null}
        </div>
        <div className="fw-panel-actions">
          <button
            type="button"
            className="action-btn"
            id="firewall-add"
            disabled={locked}
            onClick={() => {
              setFormMode("create");
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <IconPlus />
            Add rule
          </button>
          <button
            type="button"
            className="action-btn"
            id="firewall-import"
            disabled={locked}
            onClick={() => setImportOpen(true)}
          >
            Import
          </button>
          <button
            type="button"
            className="action-btn"
            id="firewall-export"
            disabled={locked}
            onClick={() => void onExportClick()}
          >
            Export
          </button>
          <button
            type="button"
            className={saving ? "action-btn btn-primary is-loading" : "action-btn btn-primary"}
            id="firewall-save"
            disabled={locked || !dirty}
            aria-busy={saving}
            onClick={() => void persist(rules)}
          >
            {saving ? (
              <span className="spinner refresh-spinner" aria-hidden="true" />
            ) : null}
            Save &amp; apply
          </button>
        </div>
      </div>

      <FirewallRecommendations
        items={props.recommendations}
        busy={locked}
        onApply={applyRecommendation}
        onDismiss={props.onDismissRecommendation}
      />

      {rules.length === 0 ? (
        <p className="muted" id="firewall-empty">
          No firewall rules. Apply a recommendation, add a row, or import — then
          Save.
        </p>
      ) : (
        <div className="fw-table-wrap">
          <table className="fw-table" id="firewall-table">
            <thead>
              <tr>
                <th className="fw-col-grip" aria-label="Reorder" />
                <th>#</th>
                <th>CIDR</th>
                <th>Port</th>
                <th>Protocol</th>
                <th>Service</th>
                <th>Action</th>
                <th>Id</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, index) => (
                <tr
                  key={rule.id}
                  data-fw-rule-id={rule.id}
                  draggable={!locked}
                  onDragStart={() => setDragIndex(index)}
                  onDragOver={(e: DragEvent) => e.preventDefault()}
                  onDrop={() => onDrop(index)}
                  onDragEnd={() => setDragIndex(null)}
                  className={dragIndex === index ? "fw-row-dragging" : undefined}
                >
                  <td className="fw-col-grip">
                    <span className="fw-grip" title="Drag to reorder">
                      <IconGrip />
                    </span>
                  </td>
                  <td>{index + 1}</td>
                  <td>
                    <code>{rule.cidr}</code>
                  </td>
                  <td>{formatFirewallPort(rule.port)}</td>
                  <td>{rule.protocol}</td>
                  <td>{rule.service}</td>
                  <td>
                    <span className={`fw-action fw-action--${rule.action}`}>
                      {rule.action}
                    </span>
                  </td>
                  <td>{rule.id}</td>
                  <td>
                    <div className="fw-row-actions">
                      <IconAction
                        label="Move up"
                        disabled={locked || index === 0}
                        onClick={() => move(index, -1)}
                      >
                        <IconChevronUp />
                      </IconAction>
                      <IconAction
                        label="Move down"
                        disabled={locked || index === rules.length - 1}
                        onClick={() => move(index, 1)}
                      >
                        <IconChevronDown />
                      </IconAction>
                      <IconAction
                        label="Edit"
                        disabled={locked}
                        onClick={() => {
                          setFormMode("edit");
                          setEditing(rule);
                          setFormOpen(true);
                        }}
                      >
                        <IconPencil />
                      </IconAction>
                      <IconAction
                        label="Remove"
                        disabled={locked}
                        danger
                        onClick={() => setPendingDelete(rule)}
                      >
                        <IconTrash />
                      </IconAction>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <FirewallRuleFormModal
        open={formOpen}
        mode={formMode}
        rule={editing}
        services={props.services}
        busy={formBusy}
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
          if (!pendingDelete) return;
          const id = pendingDelete.id;
          setPendingDelete(null);
          setRules(rules.filter((r) => r.id !== id));
        }}
      />

      <Modal
        open={importOpen}
        onClose={importBusy ? () => undefined : () => setImportOpen(false)}
        title="Import firewall"
        closeOnOverlay={!importBusy}
        footer={
          <div className="fw-import-actions">
            <button
              type="button"
              className="action-btn"
              disabled={importBusy}
              onClick={() => setImportOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="action-btn"
              id="firewall-import-confirm"
              disabled={importBusy || !importText.trim()}
              onClick={() => void onImportConfirm()}
            >
              Import &amp; apply
            </button>
          </div>
        }
      >
        <p className="muted">
          Paste a JSON document with version and rules (export format).
        </p>
        <textarea
          id="firewall-import-text"
          className="fw-import-area"
          value={importText}
          disabled={importBusy}
          onChange={(e) => setImportText(e.target.value)}
          spellCheck={false}
        />
      </Modal>
    </section>
  );
}

function useUnsavedGuard(dirty: boolean): void {
  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty]);
}

function IconAction(props: {
  label: string;
  disabled?: boolean;
  danger?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={props.danger ? "fw-icon-btn fw-icon-danger" : "fw-icon-btn"}
      title={props.label}
      aria-label={props.label}
      disabled={props.disabled}
      onClick={props.onClick}
    >
      {props.children}
    </button>
  );
}
