import type { GitopsHostDoc } from "./temporaryOverrideMessages";
import {
  TEMPORARY_OVERRIDE_TITLE,
  temporaryOverrideLead,
} from "./temporaryOverrideMessages";
import "./gitops.css";

type Props = {
  doc: GitopsHostDoc;
  /** Element id prefix (default: derived from doc). */
  id?: string;
};

/** Page-level note: Save applies on this host only. */
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
    </aside>
  );
}
