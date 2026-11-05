import { toast } from "../chrome/toast";
import {
  disableTipsYamlSnippet,
  type GitopsHostDoc,
} from "./temporaryOverrideMessages";
import "./gitops.css";

type Props = {
  /** Tips-bearing GitOps doc (firewall / alerts). */
  doc: Extract<GitopsHostDoc, "firewall.yaml" | "alerts.yaml">;
  id?: string;
};

/**
 * Copy-YAML helper: durable tip dismissal is ``disable_tips: true`` in the
 * ops-repo file, not click-ops dismiss JSON.
 */
export function DisableTipsCopyHint(props: Props) {
  const id = props.id ?? `gitops-disable-tips-${props.doc.replace(".yaml", "")}`;
  const snippet = disableTipsYamlSnippet();

  async function copy() {
    try {
      await navigator.clipboard.writeText(snippet.trimEnd());
      toast.good(`Copied disable_tips snippet for host/${props.doc}`);
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Copy failed");
    }
  }

  return (
    <aside className="callout gitops-disable-tips" id={id} role="note">
      <h2>Durable tip dismissal</h2>
      <p>
        Host dismiss is temporary. For a lasting hide, set{" "}
        <code>disable_tips: true</code> on <code>host/{props.doc}</code> in the
        GitOps repo, then Sync.
      </p>
      <pre className="gitops-disable-tips-snippet" tabIndex={0}>
        {snippet}
      </pre>
      <button
        type="button"
        className="btn btn-sm"
        id={`${id}-copy`}
        onClick={() => void copy()}
      >
        Copy YAML
      </button>
    </aside>
  );
}
