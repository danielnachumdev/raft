import type { NotificationChannel } from "../notifications/notificationsApi";
import type { AlertStatusPayload } from "./alertsApi";
import {
  routingLabel,
  ruleStateChip,
  ruleStateFor,
  severityChip,
  summarizeCondition,
  type AlertCatalogPayload,
  type AlertRule,
} from "./alertsHelpers";

export type AlertRuleHandlers = {
  onToggle: (rule: AlertRule) => void;
  onEdit: (rule: AlertRule) => void;
  onDryRun: (rule: AlertRule) => void;
  onTest: (rule: AlertRule) => void;
  onDelete: (rule: AlertRule) => void;
};

type Props = AlertRuleHandlers & {
  rules: AlertRule[];
  status: AlertStatusPayload | null;
  catalog: AlertCatalogPayload | null;
  channels: NotificationChannel[];
  busyId: string | null;
  canTest: boolean;
};

/** Rule rows: name + state/severity chips, condition summary, compact actions. */
export function AlertRuleList(props: Props) {
  return (
    <ul className="item-list alert-rule-list">
      {props.rules.map((rule) => (
        <AlertRuleRow key={rule.id} rule={rule} {...props} />
      ))}
    </ul>
  );
}

function AlertRuleRow(props: Props & { rule: AlertRule }) {
  const { rule } = props;
  const state = ruleStateFor(props.status, rule.id, rule.enabled);
  return (
    <li
      className={rule.enabled ? "item-row alert-rule-row" : "item-row alert-rule-row is-disabled"}
      data-rule-id={rule.id}
      id={`alert-rule-${rule.id}`}
    >
      <div className="alert-rule-main">
        <div className="alert-rule-title">
          <strong>{rule.name}</strong>
          <code className="alert-rule-id">{rule.id}</code>
        </div>
        <div className="alert-rule-chips">
          <span className={ruleStateChip(state)}>{state}</span>
          <span className={severityChip(rule.severity)}>{rule.severity}</span>
        </div>
        <p className="alert-rule-summary">
          <code>{summarizeCondition(rule.condition, props.catalog ?? undefined)}</code>
          <span>for {rule.for}</span>
          <span>cool-down {rule.cooldown}</span>
          <span>→ {routingLabel(rule.channelIds, props.channels)}</span>
        </p>
        {rule.description ? <p className="alert-rule-desc muted">{rule.description}</p> : null}
      </div>
      <RuleActions {...props} />
    </li>
  );
}

function RuleActions(props: Props & { rule: AlertRule }) {
  const { rule } = props;
  const busy = props.busyId === rule.id;
  return (
    <div className="btn-group item-row-actions">
      <button type="button" className="btn btn-sm" id={`alert-edit-${rule.id}`} onClick={() => props.onEdit(rule)}>
        Edit
      </button>
      <button
        type="button"
        className="btn btn-sm"
        id={`alert-toggle-${rule.id}`}
        disabled={busy}
        onClick={() => props.onToggle(rule)}
      >
        {rule.enabled ? "Disable" : "Enable"}
      </button>
      <button
        type="button"
        className="btn btn-sm"
        id={`alert-dryrun-${rule.id}`}
        disabled={busy}
        title="Evaluate now without notifying"
        onClick={() => props.onDryRun(rule)}
      >
        Dry run
      </button>
      <button
        type="button"
        className="btn btn-sm"
        id={`alert-test-${rule.id}`}
        disabled={busy || !props.canTest}
        title={props.canTest ? "Send a test notification" : "No deliverable channel"}
        onClick={() => props.onTest(rule)}
      >
        Send test
      </button>
      <button
        type="button"
        className="btn btn-sm btn-danger"
        id={`alert-delete-${rule.id}`}
        disabled={busy}
        onClick={() => props.onDelete(rule)}
      >
        Delete
      </button>
    </div>
  );
}
