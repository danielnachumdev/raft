import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "../chrome/Modal";
import type {
  FirewallAction,
  FirewallRule,
  FirewallServiceOption,
} from "./firewallApi";
import "../acl/AclPanel.css";

const PROTOCOLS = ["tcp", "udp", "http", "https", "icmp", "other"] as const;
const ACTIONS: FirewallAction[] = ["permit", "deny", "drop"];

export type FirewallRuleFormSubmit = FirewallRule;

type Props = {
  open: boolean;
  mode: "create" | "edit";
  rule: FirewallRule | null;
  services: FirewallServiceOption[];
  busy: boolean;
  onClose: () => void;
  onSubmit: (body: FirewallRuleFormSubmit) => void;
};

/** Modal to create or edit one ordered firewall row. */
export function FirewallRuleFormModal(props: Props) {
  const [id, setId] = useState("");
  const [cidr, setCidr] = useState("");
  const [port, setPort] = useState("443");
  const [protocol, setProtocol] = useState("tcp");
  const [protocolOther, setProtocolOther] = useState("");
  const [service, setService] = useState("any");
  const [action, setAction] = useState<FirewallAction>("permit");

  useEffect(() => {
    if (!props.open) return;
    const known = new Set<string>(PROTOCOLS.filter((p) => p !== "other"));
    const proto = props.rule?.protocol ?? "tcp";
    const isOther = proto !== "" && !known.has(proto);
    setId(props.rule?.id ?? "");
    setCidr(props.rule?.cidr ?? "");
    setPort(String(props.rule?.port ?? 443));
    setProtocol(isOther ? "other" : proto);
    setProtocolOther(isOther ? proto : "");
    setService(props.rule?.service ?? "any");
    setAction(props.rule?.action ?? "permit");
  }, [props.open, props.rule]);

  const resolvedProtocol =
    protocol === "other" ? protocolOther.trim().toLowerCase() : protocol;
  const portNum = Number(port);
  const canSave =
    id.trim() !== "" &&
    cidr.trim() !== "" &&
    Number.isInteger(portNum) &&
    portNum >= 1 &&
    portNum <= 65535 &&
    resolvedProtocol !== "" &&
    service.trim() !== "" &&
    !props.busy;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSave) return;
    props.onSubmit({
      id: id.trim(),
      cidr: cidr.trim(),
      port: portNum,
      protocol: resolvedProtocol,
      service: service.trim(),
      action,
    });
  }

  const title = props.mode === "create" ? "Add rule" : "Edit rule";

  return (
    <Modal
      open={props.open}
      onClose={props.busy ? () => undefined : props.onClose}
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
            form="firewall-rule-form"
            className={props.busy ? "action-btn is-loading" : "action-btn"}
            disabled={!canSave}
            aria-busy={props.busy}
            id="firewall-rule-save"
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
        id="firewall-rule-form"
        className="acl-entry-form"
        onSubmit={(e) => void onSubmit(e)}
      >
        <label className="deploy-label">
          Id
          <input
            id="firewall-rule-id"
            value={id}
            disabled={props.busy || props.mode === "edit"}
            onChange={(e) => setId(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label className="deploy-label">
          CIDR
          <input
            id="firewall-rule-cidr"
            value={cidr}
            disabled={props.busy}
            onChange={(e) => setCidr(e.target.value)}
            placeholder="192.0.2.0/24"
            autoComplete="off"
          />
        </label>
        <label className="deploy-label">
          Port
          <input
            id="firewall-rule-port"
            type="number"
            min={1}
            max={65535}
            value={port}
            disabled={props.busy}
            onChange={(e) => setPort(e.target.value)}
          />
        </label>
        <label className="deploy-label">
          Protocol
          <select
            id="firewall-rule-protocol"
            value={protocol}
            disabled={props.busy}
            onChange={(e) => setProtocol(e.target.value)}
          >
            {PROTOCOLS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        {protocol === "other" ? (
          <label className="deploy-label">
            Other protocol
            <input
              id="firewall-rule-protocol-other"
              value={protocolOther}
              disabled={props.busy}
              onChange={(e) => setProtocolOther(e.target.value)}
              autoComplete="off"
            />
          </label>
        ) : null}
        <label className="deploy-label">
          Service
          <select
            id="firewall-rule-service"
            value={service}
            disabled={props.busy}
            onChange={(e) => setService(e.target.value)}
          >
            {props.services.map((svc) => (
              <option key={svc.name} value={svc.name}>
                {svc.label || svc.name}
              </option>
            ))}
          </select>
        </label>
        <label className="deploy-label">
          Action
          <select
            id="firewall-rule-action"
            value={action}
            disabled={props.busy}
            onChange={(e) => setAction(e.target.value as FirewallAction)}
          >
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
      </form>
    </Modal>
  );
}
