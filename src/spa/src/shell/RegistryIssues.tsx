import type { RegistryIssue } from "../shared/api/index.ts";

/** Warning callout for applied manifests that failed to parse. */
export function RegistryIssues(props: { issues: RegistryIssue[] }) {
  if (!props.issues.length) return null;
  return (
    <section className="callout callout-warn registry-issues" id="registry-issues">
      <h2>
        {props.issues.length === 1
          ? "1 App manifest could not be loaded"
          : `${props.issues.length} App manifests could not be loaded`}
      </h2>
      <p className="muted">
        These files under <code>services/</code> were skipped so other
        services keep working. Fix or remove them, then refresh. Apply/deploy
        still rejects bad YAML with a clear error.
      </p>
      <ul className="registry-issue-list">
        {props.issues.map((issue) => (
          <li key={issue.file}>
            <code>{issue.file}</code>
            <p className="error" role="alert">
              {issue.error}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
