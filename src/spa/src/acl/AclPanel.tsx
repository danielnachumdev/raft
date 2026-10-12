import { useEffect, useState } from "react";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { toast } from "../chrome/toast";
import type { AclEntry, AclMode, AclPolicy } from "./aclApi";
import { AclEntryFormModal, type AclEntryFormSubmit } from "./AclEntryFormModal";
import "./AclPanel.css";

type Props = {
  title: string;
  description: string;
  policy: AclPolicy;
  busy: boolean;
  idPrefix: string;
  onSave: (policy: AclPolicy) => Promise<void>;
  onClear: () => Promise<void>;
};

/** Shared whitelist/blacklist editor (gate or per-App). */
export function AclPanel(props: Props) {
  const [mode, setMode] = useState<AclMode>(props.policy.mode);
  const [entries, setEntries] = useState<AclEntry[]>(props.policy.entries);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [editing, setEditing] = useState<AclEntry | null>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AclEntry | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMode(props.policy.mode);
    setEntries(props.policy.entries);
  }, [props.policy]);

  async function persist(next: AclPolicy) {
    setSaving(true);
    try {
      await props.onSave(next);
      setMode(next.mode);
      setEntries(next.entries);
      toast.good("Access rules applied (gate nginx reload)");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Failed to save ACL");
    } finally {
      setSaving(false);
    }
  }

  async function onModeChange(nextMode: AclMode) {
    setMode(nextMode);
    if (nextMode === "off") {
      await persist({ mode: "off", entries: [] });
      return;
    }
    if (entries.length === 0) {
      toast.regular("Add at least one CIDR before enabling whitelist/blacklist");
      return;
    }
    await persist({ mode: nextMode, entries });
  }

  async function onFormSubmit(body: AclEntryFormSubmit) {
    setFormBusy(true);
    try {
      const nextEntries =
        formMode === "create"
          ? [...entries.filter((e) => e.id !== body.id), body]
          : entries.map((e) => (e.id === body.id ? body : e));
      const nextMode = mode === "off" ? "whitelist" : mode;
      await persist({ mode: nextMode, entries: nextEntries });
      setFormOpen(false);
      setEditing(null);
    } finally {
      setFormBusy(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const entry = pendingDelete;
    setPendingDelete(null);
    const nextEntries = entries.filter((e) => e.id !== entry.id);
    if (nextEntries.length === 0) {
      await persist({ mode: "off", entries: [] });
      return;
    }
    await persist({ mode, entries: nextEntries });
  }

  return (
    <section className="panel acl-panel" id={`${props.idPrefix}-panel`}>
      <div className="acl-panel-head">
        <div>
          <h2>{props.title}</h2>
          <p className="muted">{props.description}</p>
        </div>
        <div className="acl-panel-actions">
          <label className="deploy-label acl-mode-label">
            Mode
            <select
              id={`${props.idPrefix}-mode`}
              value={mode}
              disabled={props.busy || saving}
              onChange={(e) => void onModeChange(e.target.value as AclMode)}
            >
              <option value="off">Off</option>
              <option value="whitelist">Whitelist</option>
              <option value="blacklist">Blacklist</option>
            </select>
          </label>
          <button
            type="button"
            className="action-btn"
            id={`${props.idPrefix}-add`}
            disabled={props.busy || saving}
            onClick={() => {
              setFormMode("create");
              setEditing(null);
              setFormOpen(true);
            }}
          >
            Add CIDR
          </button>
          <button
            type="button"
            className="action-btn"
            id={`${props.idPrefix}-clear`}
            disabled={props.busy || saving || mode === "off"}
            onClick={() => void props.onClear()}
          >
            Clear all
          </button>
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="muted" id={`${props.idPrefix}-empty`}>
          No CIDR entries. Mode is off until you add one and choose
          whitelist/blacklist.
        </p>
      ) : (
        <ul className="acl-entry-list" id={`${props.idPrefix}-list`}>
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="acl-entry-row"
              data-acl-entry-id={entry.id}
            >
              <div>
                <strong>{entry.id}</strong>
                <code className="acl-cidr">{entry.cidr}</code>
                {entry.comment ? (
                  <span className="muted"> — {entry.comment}</span>
                ) : null}
              </div>
              <div className="acl-entry-actions">
                <button
                  type="button"
                  className="action-btn"
                  disabled={props.busy || saving}
                  onClick={() => {
                    setFormMode("edit");
                    setEditing(entry);
                    setFormOpen(true);
                  }}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="action-btn"
                  disabled={props.busy || saving}
                  onClick={() => setPendingDelete(entry)}
                >
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <AclEntryFormModal
        open={formOpen}
        mode={formMode}
        entry={editing}
        busy={formBusy}
        onClose={() => setFormOpen(false)}
        onSubmit={(body) => void onFormSubmit(body)}
      />

      <ConfirmPopup
        open={pendingDelete !== null}
        title="Remove CIDR?"
        message={
          pendingDelete
            ? `Remove ${pendingDelete.id} (${pendingDelete.cidr}) from this ACL?`
            : ""
        }
        confirmLabel="Remove"
        danger
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => void confirmDelete()}
      />
    </section>
  );
}
