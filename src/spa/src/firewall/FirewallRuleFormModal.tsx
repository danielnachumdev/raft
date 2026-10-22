import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "../chrome/Modal";
import type {
  FirewallAction,
  FirewallPort,
  FirewallRule,
  FirewallServiceOption,
} from "./firewallApi";
import "./FirewallPanel.css";

const PROTOCOLS = ["tcp", "udp", "http", "https", "icmp", "any", "other"] as const;

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
  const [portAny, setPortAny] = useState(false);
  const [protocol, setProtocol] = useState("tcp");
  const [protocolOther, setProtocolOther] = useState("");
  const [service, setService] = useState("any");
  const [action, setAction] = useState<FirewallAction>("permit");

  useEffect(() => {
    if (!props.open) return;
    const known = new Set<string>(PROTOCOLS.filter((p) => p !== "other"));
    const proto = props.rule?.protocol ?? "tcp";
    const isOther = proto !== "" && !known.has(proto);
    const rulePort = props.rule?.port;
    const anyPort = rulePort === "any" || rulePort === 0;
    setId(props.rule?.id ?? "");
    setCidr(props.rule?.cidr ?? "");
    setPortAny(anyPort);
    setPort(anyPort ? "443" : String(rulePort ?? 443));
    setProtocol(isOther ? "other" : proto);
    setProtocolOther(isOther ? proto : "");
    setService(props.rule?.service ?? "any");
    setAction(props.rule?.action ?? "permit");
  }, [props.open, props.rule]);

  const resolvedProtocol =
    protocol === "other" ? protocolOther.trim().toLowerCase() : protocol;
  const portNum = Number(port);
  const portOk = portAny || (Number.isInteger(portNum) && portNum >= 1 && portNum <= 65535);
  const canSave =
    id.trim() !== "" &&
    cidr.trim() !== "" &&
    portOk &&
    resolvedProtocol !== "" &&
    service.trim() !== "" &&
    !props.busy;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSave) return;
    const resolvedPort: FirewallPort = portAny ? "any" : portNum;
    props.onSubmit({
      id: id.trim(),
      cidr: cidr.trim(),
      port: resolvedPort,
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
            className="btn"
            disabled={props.busy}
            onClick={props.onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="firewall-rule-form"
            className={props.busy ? "btn btn-primary is-loading" : "btn btn-primary"}
            disabled={!canSave}
            aria-busy={props.busy}
            id="firewall-rule-save"
          >
            {props.busy ? (
              <span className="spinner btn-spinner" aria-hidden="true" />
            ) : null}
            Save
          </button>
        </div>
      }
    >
      <form
        id="firewall-rule-form"
        className="fw-entry-form"
        onSubmit={(e) => void onSubmit(e)}
      >
        <label className="field">
          Id
          <input
            id="firewall-rule-id"
            value={id}
            disabled={props.busy || props.mode === "edit"}
            onChange={(e) => setId(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label className="field">
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
        <label className="field fw-check">
          <input
            type="checkbox"
            id="firewall-rule-port-any"
            checked={portAny}
            disabled={props.busy}
            onChange={(e) => setPortAny(e.target.checked)}
          />
          Port any
        </label>
        {!portAny ? (
          <label className="field">
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
        ) : null}
        <label className="field">
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
          <label className="field">
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
        <label className="field">
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
          <span className="form-hint">
            any = edge-wide; an App name is Host-scoped (needs expose: http +
            publicHost).
          </span>
        </label>
        <label className="field">
          Action
          <select
            id="firewall-rule-action"
            value={action}
            disabled={props.busy}
            onChange={(e) => setAction(e.target.value as FirewallAction)}
          >
            <option value="permit">permit (allow)</option>
            <option value="deny">deny (HTTP 403)</option>
            <option value="drop">drop (nginx 444)</option>
          </select>
        </label>
      </form>
    </Modal>
  );
}
