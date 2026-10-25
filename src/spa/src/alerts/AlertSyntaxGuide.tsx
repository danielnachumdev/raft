import { useEffect, useMemo, useState } from "react";
import { Modal } from "../chrome/Modal";
import { alertDocumentJson, alertDocumentYaml } from "./alertDocumentYaml";
import {
  ALERT_EXAMPLES_GITHUB_URL,
  ALERT_RULES_EXAMPLE_GITHUB_URL,
  ALERT_SYNTAX_EXAMPLE,
  ALERT_SYNTAX_PRIMER,
  type AlertRulesDocument,
} from "./alertSyntaxExamples";
import type { AlertRule } from "./alertsHelpers";
import "./AlertSyntaxGuide.css";

export type AlertSyntaxFormat = "yaml" | "json";

type Props = {
  open: boolean;
  rules?: AlertRule[];
  onClose: () => void;
};

/** In-app primer + YAML/JSON samples for alert rule documents. */
export function AlertSyntaxGuide(props: Props) {
  const [format, setFormat] = useState<AlertSyntaxFormat>("yaml");
  const [source, setSource] = useState<"example" | "yours">("example");
  const yours: AlertRulesDocument = useMemo(
    () => ({ version: 1, rules: props.rules ?? [] }),
    [props.rules],
  );
  const doc = source === "yours" ? yours : ALERT_SYNTAX_EXAMPLE;
  const text =
    format === "yaml" ? alertDocumentYaml(doc) : alertDocumentJson(doc);

  useEffect(() => {
    if (!props.open) return;
    setFormat("yaml");
    setSource("example");
  }, [props.open]);

  if (!props.open) return null;

  return (
    <Modal
      open
      onClose={props.onClose}
      size="wide"
      title="Alert rule syntax"
      footer={
        <div className="modal-actions">
          <a
            className="btn"
            href={ALERT_EXAMPLES_GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            id="alert-syntax-github"
          >
            Examples on GitHub
          </a>
          <button type="button" className="btn btn-primary" onClick={props.onClose}>
            Close
          </button>
        </div>
      }
    >
      <div className="alert-syntax" id="alert-syntax-guide">
        <p className="alert-syntax-lead">
          Rules live in <code>host/alerts/rules.yaml</code> (Import/Export use the same
          document). Channels are optional — a rule evaluates without them.
        </p>
        <dl className="alert-syntax-primer">
          {ALERT_SYNTAX_PRIMER.map((row) => (
            <div key={row.term} className="alert-syntax-primer-row">
              <dt>
                <code>{row.term}</code>
              </dt>
              <dd>{row.meaning}</dd>
            </div>
          ))}
        </dl>
        <div className="alert-syntax-toolbar" role="group" aria-label="Sample source">
          <FormatToggle
            id="alert-syntax-source-example"
            active={source === "example"}
            label="Demo sample"
            onClick={() => setSource("example")}
          />
          <FormatToggle
            id="alert-syntax-source-yours"
            active={source === "yours"}
            label="Your rules"
            onClick={() => setSource("yours")}
          />
          <span className="alert-syntax-toolbar-gap" aria-hidden="true" />
          <FormatToggle
            id="alert-syntax-format-yaml"
            active={format === "yaml"}
            label="YAML"
            onClick={() => setFormat("yaml")}
          />
          <FormatToggle
            id="alert-syntax-format-json"
            active={format === "json"}
            label="JSON"
            onClick={() => setFormat("json")}
          />
        </div>
        {source === "yours" && !(props.rules?.length) ? (
          <p className="form-hint" id="alert-syntax-empty-yours">
            No rules yet — showing an empty document. Add a recommendation or use the demo
            sample.
          </p>
        ) : null}
        <pre className="alert-syntax-code mono" id="alert-syntax-body" tabIndex={0}>
          {text}
        </pre>
        <p className="form-hint">
          Checked-in sample:{" "}
          <a href={ALERT_RULES_EXAMPLE_GITHUB_URL} target="_blank" rel="noreferrer">
            examples/alerts/rules.yaml
          </a>
          . Apply with Import or{" "}
          <code>raft alerts apply --file examples/alerts/rules.yaml</code>.
        </p>
      </div>
    </Modal>
  );
}

function FormatToggle(props: {
  id: string;
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      id={props.id}
      className={props.active ? "btn btn-primary" : "btn"}
      aria-pressed={props.active}
      onClick={props.onClick}
    >
      {props.label}
    </button>
  );
}
