import { RecommendationList } from "../recommendations";
import type { AlertRecommendation } from "./alertsApi";
import { summarizeCondition } from "./alertsHelpers";

type Props = {
  items: AlertRecommendation[];
  busy: boolean;
  onApply: (item: AlertRecommendation) => Promise<void>;
  onDismiss: (id: string) => Promise<void>;
};

/** Default alert-setup suggestions via the shared recommendation kit. */
export function AlertRecommendations(props: Props) {
  return (
    <RecommendationList
      items={props.items}
      busy={props.busy}
      sectionId="alert-recommendations"
      applyIdPrefix="alert-rec-apply"
      dismissIdPrefix="alert-rec-dismiss"
      lede="Suggested rules for common failure modes. Apply creates the rule immediately — notification channels are optional and can be added later."
      onApply={props.onApply}
      onDismiss={props.onDismiss}
      renderPreview={(item) => (
        <code className="alert-rec-preview">
          {summarizeCondition(item.rule.condition)} · channels optional
        </code>
      )}
    />
  );
}
