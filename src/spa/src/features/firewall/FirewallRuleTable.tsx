import { useState, type DragEvent, type ReactNode } from "react";
import type { FirewallRule } from "./firewallApi";
import { formatFirewallPort } from "./firewallApi";
import {
  IconChevronDown,
  IconChevronUp,
  IconGrip,
  IconPencil,
  IconTrash,
} from "./FirewallIcons";

type Props = {
  rules: FirewallRule[];
  locked: boolean;
  onReorder: (from: number, to: number) => void;
  onEdit: (rule: FirewallRule) => void;
  onRemove: (rule: FirewallRule) => void;
};

/** Ordered rule table: drag grip, arrows, edit/remove icon actions. */
export function FirewallRuleTable(props: Props) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const last = props.rules.length - 1;

  function onDrop(target: number) {
    if (dragIndex !== null && dragIndex !== target) props.onReorder(dragIndex, target);
    setDragIndex(null);
  }

  return (
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
            <th className="fw-col-actions" aria-label="Row actions" />
          </tr>
        </thead>
        <tbody>
          {props.rules.map((rule, index) => (
            <tr
              key={rule.id}
              data-fw-rule-id={rule.id}
              draggable={!props.locked}
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
              <td className="fw-col-index">{index + 1}</td>
              <td>
                <code>{rule.cidr}</code>
              </td>
              <td>{formatFirewallPort(rule.port)}</td>
              <td>{rule.protocol}</td>
              <td>{rule.service}</td>
              <td>
                <span className={actionChip(rule.action)}>{rule.action}</span>
              </td>
              <td className="muted">{rule.id}</td>
              <td className="fw-col-actions">
                <div className="fw-row-actions">
                  <IconAction
                    label="Move up"
                    disabled={props.locked || index === 0}
                    onClick={() => props.onReorder(index, index - 1)}
                  >
                    <IconChevronUp />
                  </IconAction>
                  <IconAction
                    label="Move down"
                    disabled={props.locked || index === last}
                    onClick={() => props.onReorder(index, index + 1)}
                  >
                    <IconChevronDown />
                  </IconAction>
                  <IconAction
                    label="Edit"
                    disabled={props.locked}
                    onClick={() => props.onEdit(rule)}
                  >
                    <IconPencil />
                  </IconAction>
                  <IconAction
                    label="Remove"
                    disabled={props.locked}
                    danger
                    onClick={() => props.onRemove(rule)}
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
  );
}

function actionChip(action: string): string {
  const tone = action === "permit" ? "chip-ok" : "chip-bad";
  return `chip ${tone} fw-action fw-action--${action}`;
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
      className={props.danger ? "btn-icon is-danger" : "btn-icon"}
      title={props.label}
      aria-label={props.label}
      disabled={props.disabled}
      onClick={props.onClick}
    >
      {props.children}
    </button>
  );
}
