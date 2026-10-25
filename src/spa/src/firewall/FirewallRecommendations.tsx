import { RecommendationList } from "../recommendations";
import type { FirewallRecommendation, FirewallRule } from "./firewallApi";
import { formatFirewallPort } from "./firewallApi";

type Props = {
  items: FirewallRecommendation[];
  busy: boolean;
  onApply: (item: FirewallRecommendation) => void;
  onDismiss: (id: string) => Promise<void>;
};

/** Baseline suggestions: per-port permit + default deny (shared recommendation kit). */
export function FirewallRecommendations(props: Props) {
  return (
    <RecommendationList
      items={props.items}
      busy={props.busy}
      sectionId="firewall-recommendations"
      applyIdPrefix="firewall-rec-apply"
      dismissIdPrefix="firewall-rec-dismiss"
      lede="Fast baseline for new stacks. Apply inserts into the table (Save still required). Dismiss hides until the baseline changes."
      onApply={props.onApply}
      onDismiss={props.onDismiss}
      renderPreview={(item) => (
        <code className="fw-rec-preview">{preview(item.rule)}</code>
      )}
    />
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
