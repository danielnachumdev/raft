import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "../chrome/Modal";
import type { NotificationChannel } from "./notificationsApi";
import {
  formatSettingsJson,
  parseSettingsJson,
  strategyTypeIds,
} from "./notificationsHelpers";
import type { NotificationStrategyInfo } from "./notificationsApi";
import "./ChannelFormModal.css";

export type ChannelFormMode = "create" | "edit";

export type ChannelFormSubmit = {
  id: string;
  type: string;
  enabled: boolean;
  settings: Record<string, unknown>;
};

type Props = {
  open: boolean;
  mode: ChannelFormMode;
  strategies: NotificationStrategyInfo[];
  channel: NotificationChannel | null;
  busy: boolean;
  onClose: () => void;
  onSubmit: (values: ChannelFormSubmit) => void | Promise<void>;
};

/** Add / edit channel dialog: catalog type + opaque settings JSON. */
export function ChannelFormModal(props: Props) {
  const catalogIds = strategyTypeIds(props.strategies);
  const typeChoices = typeChoicesFor(props.mode, props.channel, catalogIds);
  const [id, setId] = useState("");
  const [type, setType] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [settingsText, setSettingsText] = useState("{}");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!props.open) return;
    setFormError(null);
    if (props.mode === "edit" && props.channel) {
      setId(props.channel.id);
      setType(props.channel.type);
      setEnabled(props.channel.enabled);
      setSettingsText(formatSettingsJson(props.channel.settings));
      return;
    }
    setId("");
    setType(catalogIds[0] ?? "");
    setEnabled(true);
    setSettingsText("{\n  \n}");
  }, [props.open, props.mode, props.channel, catalogIds.join("|")]);

  const title = props.mode === "create" ? "Add channel" : "Edit channel";
  const typeLocked = props.mode === "edit" && catalogIds.length === 0;
  const saveDisabled =
    props.busy ||
    (props.mode === "create" && catalogIds.length === 0) ||
    (props.mode === "edit" && typeChoices.length === 0);

  return (
    <Modal
      open={props.open}
      onClose={props.busy ? noop : props.onClose}
      title={title}
      closeOnOverlay={!props.busy}
      footer={
        <div className="modal-actions">
          <button
            type="button"
            className="action-btn"
            disabled={props.busy}
            onClick={props.onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="channel-form"
            className={props.busy ? "action-btn is-loading" : "action-btn"}
            disabled={saveDisabled}
            aria-busy={props.busy}
            id="channel-form-save"
          >
            {props.busy ? (
              <span className="spinner refresh-spinner" aria-hidden="true" />
            ) : null}
            Save
          </button>
        </div>
      }
    >
      <form
        id="channel-form"
        className="channel-form"
        onSubmit={(event) => void handleSubmit(event)}
      >
        <label className="deploy-label">
          Id
          <input
            id="channel-id"
            autoComplete="off"
            value={id}
            disabled={props.busy || props.mode === "edit"}
            onChange={(e) => setId(e.target.value)}
            placeholder="ops-primary"
            required
          />
        </label>
        <label className="deploy-label">
          Type
          {typeLocked ? (
            <input id="channel-type" value={type} disabled readOnly />
          ) : (
            <select
              id="channel-type"
              value={type}
              disabled={props.busy || typeChoices.length === 0}
              onChange={(e) => setType(e.target.value)}
              required
            >
              {typeChoices.length === 0 ? (
                <option value="">No strategies registered</option>
              ) : null}
              {typeChoices.map((typeId) => (
                <option key={typeId} value={typeId}>
                  {typeId}
                </option>
              ))}
            </select>
          )}
        </label>
        <label className="channel-enabled">
          <input
            id="channel-enabled"
            type="checkbox"
            checked={enabled}
            disabled={props.busy}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          Enabled
        </label>
        <label className="deploy-label">
          Settings (JSON)
          <textarea
            id="channel-settings"
            className="channel-settings"
            value={settingsText}
            disabled={props.busy}
            onChange={(e) => setSettingsText(e.target.value)}
            spellCheck={false}
            rows={8}
          />
        </label>
        <p className="muted channel-form-hint">
          Secret fields from the API stay as <code>***</code>. Leave them
          unchanged to keep stored secrets.
        </p>
        {formError ? (
          <p className="error" role="alert" id="channel-form-error">
            {formError}
          </p>
        ) : null}
      </form>
    </Modal>
  );

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    let settings: Record<string, unknown>;
    try {
      settings = parseSettingsJson(settingsText);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Invalid settings JSON");
      return;
    }
    const trimmedId = id.trim();
    if (!trimmedId) {
      setFormError("Id is required");
      return;
    }
    if (!type.trim()) {
      setFormError("Pick a registered strategy type");
      return;
    }
    await props.onSubmit({
      id: trimmedId,
      type: type.trim(),
      enabled,
      settings,
    });
  }
}

function noop() {}

/** Catalog types for create; edit may keep an existing non-catalog type visible. */
function typeChoicesFor(
  mode: ChannelFormMode,
  channel: NotificationChannel | null,
  catalogIds: string[],
): string[] {
  if (mode === "create") return catalogIds;
  const current = channel?.type?.trim() ?? "";
  if (!current) return catalogIds;
  if (catalogIds.includes(current)) return catalogIds;
  return [current, ...catalogIds];
}
