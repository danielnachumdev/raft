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
    <section className="fw-recs" id="firewall-recommendations">
      <h3>Recommendations</h3>
      <p className="muted">
        Fast baseline for new stacks. Apply inserts into the table (Save still
        required). Dismiss hides until the baseline changes.
      </p>
      <ul className="fw-rec-list">
        {props.items.map((item) => (
          <li key={item.id} className="fw-rec-row" data-fw-rec-id={item.id}>
            <div>
              <strong>{item.title}</strong>
              <p className="muted">{item.summary}</p>
              <code className="fw-rec-preview">{preview(item.rule)}</code>
            </div>
            <div className="fw-rec-actions">
              <button
                type="button"
                className="action-btn"
                id={`firewall-rec-apply-${item.id}`}
                disabled={props.busy}
                onClick={() => props.onApply(item)}
              >
                Apply
              </button>
              <button
                type="button"
                className="action-btn"
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
