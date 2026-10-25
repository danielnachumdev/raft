import { useState, type FormEvent } from "react";
import { Modal } from "../chrome/Modal";
import type { NotificationChannel } from "../notifications/notificationsApi";
import { validateDraft, type AlertCatalogPayload, type AlertRule } from "./alertsHelpers";

export type AlertFormMode = "create" | "edit";

type Props = {
  mode: AlertFormMode;
  initial: AlertRule;
  catalog: AlertCatalogPayload | null;
  channels: NotificationChannel[];
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (rule: AlertRule) => void | Promise<void>;
  /** Open the shared YAML/JSON syntax guide (page-owned modal). */
  onOpenSyntax?: () => void;
};

/** Add / edit alert rule dialog (typed basics + advanced condition JSON). Mount per open. */
export function AlertRuleFormModal(props: Props) {
  const [draft, setDraft] = useState<AlertRule>(() => ({
    ...props.initial,
    channelIds: [...props.initial.channelIds],
  }));
  const [conditionText, setConditionText] = useState(() =>
    JSON.stringify(props.initial.condition, null, 2),
  );
  const [localError, setLocalError] = useState<string | null>(null);
  const set = (patch: Partial<AlertRule>) => setDraft({ ...draft, ...patch });
  const conditionError = parseError(conditionText);
  const shownError = localError ?? props.error;

  return (
    <Modal
      open
      onClose={props.busy ? noop : props.onClose}
      closeOnOverlay={!props.busy}
      size="wide"
      title={props.mode === "create" ? "Add alert rule" : "Edit alert rule"}
      footer={<FormFooter busy={props.busy} invalid={!!conditionError} onCancel={props.onClose} />}
    >
      <form id="alert-rule-form" className="alert-form" onSubmit={submit}>
        <div className="form-grid">
          <label className="field">
            Id
            <input
              id="alert-id"
              value={draft.id}
              placeholder="demo-api-5xx-rate"
              autoComplete="off"
              disabled={props.mode === "edit" || props.busy}
              onChange={(e) => set({ id: e.target.value })}
            />
          </label>
          <label className="field">
            Name
            <input
              id="alert-name"
              value={draft.name}
              placeholder="demo-api 5xx error rate"
              disabled={props.busy}
              onChange={(e) => set({ name: e.target.value })}
            />
          </label>
        </div>
        <label className="field">
          Description
          <textarea
            id="alert-description"
            rows={2}
            value={draft.description}
            disabled={props.busy}
            onChange={(e) => set({ description: e.target.value })}
          />
        </label>
        <div className="form-grid">
          <label className="field">
            Severity
            <select
              id="alert-severity"
              value={draft.severity}
              disabled={props.busy}
              onChange={(e) => set({ severity: e.target.value })}
            >
              {(props.catalog?.severities ?? [draft.severity]).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <DurationField
            label="For"
            id="alert-for"
            value={draft.for}
            busy={props.busy}
            hint="How long the condition must stay true before firing"
            onChange={(v) => set({ for: v })}
          />
          <DurationField
            label="Cool-down"
            id="alert-cooldown"
            value={draft.cooldown}
            busy={props.busy}
            hint="Silence before re-notifying the same firing instance"
            onChange={(v) => set({ cooldown: v })}
          />
        </div>
        <div className="alert-form-toggles">
          <label className="check">
            <input
              type="checkbox"
              id="alert-enabled"
              checked={draft.enabled}
              disabled={props.busy}
              onChange={(e) => set({ enabled: e.target.checked })}
            />
            Enabled
          </label>
          <label className="check">
            <input
              type="checkbox"
              id="alert-notify-recovery"
              checked={draft.notifyOnRecovery}
              disabled={props.busy}
              onChange={(e) => set({ notifyOnRecovery: e.target.checked })}
            />
            Notify on recovery
          </label>
        </div>
        <ChannelPicker
          channels={props.channels}
          selected={draft.channelIds}
          busy={props.busy}
          onChange={(channelIds) => set({ channelIds })}
        />
        <label className="field">
          Condition (JSON)
          <textarea
            id="alert-condition"
            className="alert-condition-json mono"
            rows={9}
            spellCheck={false}
            value={conditionText}
            disabled={props.busy}
            aria-invalid={!!conditionError}
            onChange={(e) => setConditionText(e.target.value)}
          />
          <span className={conditionError ? "form-error" : "form-hint"}>
            {conditionError ?? (
              <>
                Signal, select, kind, and params. Nested all/any groups are supported.{" "}
                {props.onOpenSyntax ? (
                  <button
                    type="button"
                    className="linkish"
                    id="alert-condition-syntax"
                    disabled={props.busy}
                    onClick={props.onOpenSyntax}
                  >
                    View YAML/JSON syntax
                  </button>
                ) : null}
              </>
            )}
          </span>
        </label>
        {shownError ? (
          <p className="callout callout-bad form-error" id="alert-form-error" role="alert">
            {shownError}
          </p>
        ) : null}
      </form>
    </Modal>
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    if (conditionError) return;
    const next = { ...draft, condition: JSON.parse(conditionText) as AlertRule["condition"] };
    const problems = validateDraft(next);
    if (problems.length) {
      setLocalError(problems[0]);
      return;
    }
    setLocalError(null);
    void props.onSubmit(next);
  }
}

function DurationField(props: {
  label: string;
  id: string;
  value: string;
  busy: boolean;
  hint?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      {props.label}
      <input
        id={props.id}
        value={props.value}
        placeholder="5m"
        disabled={props.busy}
        onChange={(e) => props.onChange(e.target.value)}
      />
      {props.hint ? <span className="form-hint">{props.hint}</span> : null}
    </label>
  );
}

function ChannelPicker(props: {
  channels: NotificationChannel[];
  selected: string[];
  busy: boolean;
  onChange: (ids: string[]) => void;
}) {
  const chosen = new Set(props.selected);
  const toggle = (id: string, on: boolean) =>
    props.onChange(on ? [...props.selected, id] : props.selected.filter((x) => x !== id));
  return (
    <fieldset className="alert-channels" id="alert-channels">
      <legend>Deliver to</legend>
      {props.channels.length === 0 ? (
        <p className="form-hint">
          No channels yet — you can still save this rule. Delivery starts after you add a channel under
          Notifications.
        </p>
      ) : (
        props.channels.map((c) => (
          <label key={c.id} className="check">
            <input
              type="checkbox"
              checked={chosen.has(c.id)}
              disabled={props.busy}
              onChange={(e) => toggle(c.id, e.target.checked)}
            />
            <code>{c.id}</code>
            {!c.enabled ? <span className="chip">disabled</span> : null}
          </label>
        ))
      )}
      <p className="form-hint">
        Optional. Leave all unchecked to deliver to every enabled channel when any exist.
      </p>
    </fieldset>
  );
}

function FormFooter(props: { busy: boolean; invalid: boolean; onCancel: () => void }) {
  return (
    <div className="modal-actions">
      <button type="button" className="btn" disabled={props.busy} onClick={props.onCancel}>
        Cancel
      </button>
      <button
        type="submit"
        form="alert-rule-form"
        id="alert-form-save"
        className={props.busy ? "btn btn-primary is-loading" : "btn btn-primary"}
        disabled={props.busy || props.invalid}
        aria-busy={props.busy}
      >
        {props.busy ? <span className="spinner btn-spinner" aria-hidden="true" /> : null}
        Save rule
      </button>
    </div>
  );
}

function parseError(text: string): string | null {
  try {
    const value = JSON.parse(text) as unknown;
    return value && typeof value === "object" ? null : "Condition must be a JSON object.";
  } catch (err) {
    return `Invalid JSON: ${err instanceof Error ? err.message : "parse error"}`;
  }
}

function noop() {}
