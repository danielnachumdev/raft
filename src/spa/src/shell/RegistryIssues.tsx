import type { RegistryIssue } from "../shared/api/index.ts";

/** Warning callout when some applied apps failed to load. */
export function RegistryIssues(props: { issues: RegistryIssue[] }) {
  if (!props.issues.length) return null;
  const n = props.issues.length;
  return (
    <section className="callout callout-warn registry-issues" id="registry-issues">
      <h2>
        {n === 1
          ? "1 app could not be loaded"
          : `${n} apps could not be loaded`}
      </h2>
      <p className="muted">
        Other services are unaffected. Ask an admin to fix the broken apps, then
        refresh.
      </p>
    </section>
  );
}
