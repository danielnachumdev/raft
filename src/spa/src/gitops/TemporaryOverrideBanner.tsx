import type { GitopsHostDoc } from "./temporaryOverrideMessages";
import {
  TEMPORARY_OVERRIDE_TITLE,
  temporaryOverrideGuidance,
  temporaryOverrideLead,
} from "./temporaryOverrideMessages";
import "./gitops.css";

type Props = {
  doc: GitopsHostDoc;
  /** Element id prefix (default: derived from doc). */
  id?: string;
};

/**
 * Page-level warning: Save is a temporary host override wiped by the next
 * GitOps sync of the named flat doc (CD overwrite — raft does not auto-revert).
 */
export function TemporaryOverrideBanner(props: Props) {
  const id =
    props.id ?? `gitops-temp-override-${props.doc.replace(".yaml", "")}`;
  return (
    <aside
      className="callout callout-warn gitops-temp-override"
      id={id}
      role="status"
    >
      <h2>{TEMPORARY_OVERRIDE_TITLE}</h2>
      <p>{temporaryOverrideLead(props.doc)}</p>
      <p className="gitops-temp-override-guidance">
        {temporaryOverrideGuidance(props.doc)}
      </p>
    </aside>
  );
}
