import { useEffect, useMemo, useState } from "react";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { Modal } from "../chrome/Modal";
import { toast } from "../chrome/toast";
import type {
  FirewallDocument,
  FirewallRule,
  FirewallServiceOption,
} from "./firewallApi";
import {
  FirewallRuleFormModal,
  type FirewallRuleFormSubmit,
} from "./FirewallRuleFormModal";
import "./FirewallPanel.css";

type Props = {
  document: FirewallDocument;
  services: FirewallServiceOption[];
  busy: boolean;
  onSave: (doc: Pick<FirewallDocument, "version" | "rules">) => Promise<void>;
  onExport: () => Promise<FirewallDocument>;
  onImport: (body: unknown) => Promise<void>;
  onClear: () => Promise<void>;
};

/** Ordered firewall table with Save / import / export. */
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

  useEffect(() => {
    setRules(props.document.rules);
    setSaved(props.document.rules);
  }, [props.document]);

  const dirty = useMemo(
    () => JSON.stringify(rules) !== JSON.stringify(saved),
    [rules, saved],
  );

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

  async function onFormSubmit(body: FirewallRuleFormSubmit) {
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
            Ordered table (first match wins). Save compiles to gate nginx and
            reloads — never recreate.{" "}
            {props.document.source === "acl-v1-migrated"
              ? "Showing migrated ACL v1 rules until you Save."
              : null}
          </p>
          {dirty ? (
            <p className="fw-dirty" id="firewall-dirty">
              Unsaved changes
            </p>
          ) : null}
        </div>
        <div className="fw-panel-actions">
          <button
            type="button"
            className="action-btn"
            id="firewall-add"
            disabled={props.busy || saving}
            onClick={() => {
              setFormMode("create");
              setEditing(null);
              setFormOpen(true);
            }}
          >
            Add rule
          </button>
          <button
            type="button"
            className="action-btn"
            id="firewall-save"
            disabled={props.busy || saving || !dirty}
            onClick={() => void persist(rules)}
          >
            Save
          </button>
          <button
            type="button"
            className="action-btn"
            id="firewall-export"
            disabled={props.busy || saving}
            onClick={() => void onExportClick()}
          >
            Export
          </button>
          <button
            type="button"
            className="action-btn"
            id="firewall-import"
            disabled={props.busy || saving}
            onClick={() => setImportOpen(true)}
          >
            Import
          </button>
          <button
            type="button"
            className="action-btn"
            id="firewall-clear"
            disabled={props.busy || saving || rules.length === 0}
            onClick={() => void props.onClear()}
          >
            Clear all
          </button>
        </div>
      </div>

      {rules.length === 0 ? (
        <p className="muted" id="firewall-empty">
          No firewall rules. Add a row or import a document, then Save.
        </p>
      ) : (
        <div className="fw-table-wrap">
          <table className="fw-table" id="firewall-table">
            <thead>
              <tr>
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
                <tr key={rule.id} data-fw-rule-id={rule.id}>
                  <td>{index + 1}</td>
                  <td>
                    <code>{rule.cidr}</code>
                  </td>
                  <td>{rule.port}</td>
                  <td>{rule.protocol}</td>
                  <td>{rule.service}</td>
                  <td>{rule.action}</td>
                  <td>{rule.id}</td>
                  <td>
                    <div className="fw-row-actions">
                      <button
                        type="button"
                        className="action-btn"
                        disabled={props.busy || saving || index === 0}
                        onClick={() => move(index, -1)}
                      >
                        Up
                      </button>
                      <button
                        type="button"
                        className="action-btn"
                        disabled={
                          props.busy || saving || index === rules.length - 1
                        }
                        onClick={() => move(index, 1)}
                      >
                        Down
                      </button>
                      <button
                        type="button"
                        className="action-btn"
                        disabled={props.busy || saving}
                        onClick={() => {
                          setFormMode("edit");
                          setEditing(rule);
                          setFormOpen(true);
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="action-btn"
                        disabled={props.busy || saving}
                        onClick={() => setPendingDelete(rule)}
                      >
                        Remove
                      </button>
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
        onSubmit={(body) => void onFormSubmit(body)}
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
