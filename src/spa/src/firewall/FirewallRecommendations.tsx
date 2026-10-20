import { toast } from "../chrome/toast";
import type { FirewallRecommendation, FirewallRule } from "./firewallApi";
import { formatFirewallPort } from "./firewallApi";

type Props = {
  items: FirewallRecommendation[];
  busy: boolean;
  onApply: (item: FirewallRecommendation) => void;
  onDismiss: (id: string) => Promise<void>;
};

/** Baseline suggestions: per-port permit + default deny. */
export function FirewallRecommendations(props: Props) {
  if (props.items.length === 0) return null;

  async function dismiss(id: string) {
    try {
      await props.onDismiss(id);
      toast.good("Recommendation dismissed");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Dismiss failed");
    }
  }

  return (
    <section className="panel" id="firewall-recommendations">
      <div className="panel-head">
        <h2>
          Recommendations
          <span className="panel-count">{props.items.length}</span>
        </h2>
      </div>
      <p className="panel-lede">
        Fast baseline for new stacks. Apply inserts into the table (Save still
        required). Dismiss hides until the baseline changes.
      </p>
      <ul className="item-list">
        {props.items.map((item) => (
          <li key={item.id} className="item-row" data-fw-rec-id={item.id}>
            <div className="item-row-main">
              <div className="item-row-title">
                <strong>{item.title}</strong>
              </div>
              <p className="item-row-meta">{item.summary}</p>
              <p className="item-row-meta">
                <code className="fw-rec-preview">{preview(item.rule)}</code>
              </p>
            </div>
            <div className="btn-group item-row-actions">
              <button
                type="button"
                className="btn btn-sm"
                id={`firewall-rec-apply-${item.id}`}
                disabled={props.busy}
                onClick={() => props.onApply(item)}
              >
                Apply
              </button>
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                id={`firewall-rec-dismiss-${item.id}`}
                disabled={props.busy}
                onClick={() => void dismiss(item.id)}
              >
                Dismiss
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function preview(rule: FirewallRule): string {
  return [
    rule.cidr,
    formatFirewallPort(rule.port),
    rule.protocol,
    rule.service,
    rule.action,
  ].join(" / ");
}
