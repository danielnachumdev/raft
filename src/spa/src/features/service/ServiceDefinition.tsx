import { useCallback, useEffect, useState } from "react";
import {
  fetchServiceDefinition,
  type ServiceDefinitionPayload,
} from "../../shared/api";
import { SkeletonBone, showSkeleton } from "../../shared/chrome/skeleton";
import { YamlHighlighter } from "../settings/YamlHighlighter";
import { ErrorState } from "../../shared/chrome/StateViews";
import "./ServiceDefinition.css";

const highlighter = new YamlHighlighter();

/** Applied App manifest (``services/<name>/app.yaml``) for diagnostics. */
export function ServiceDefinition(props: { service: string }) {
  const [data, setData] = useState<ServiceDefinitionPayload | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const payload = await fetchServiceDefinition(props.service);
      setData(payload);
      setError(null);
    } catch {
      setError("Failed to load App definition.");
    } finally {
      setBusy(false);
    }
  }, [props.service]);

  useEffect(() => {
    setBusy(true);
    void load();
  }, [load]);

  if (!busy && data && !data.eligible) {
    return null;
  }

  return (
    <section className="panel service-definition" aria-labelledby="definition-title">
      <div className="service-definition-head">
        <h2 id="definition-title">Definition</h2>
        {data?.path ? (
          <code className="muted service-definition-path">{data.path}</code>
        ) : null}
      </div>
      {showSkeleton(busy, data !== null) && !error ? (
        <div
          className="skeleton-block-panel"
          role="status"
          aria-busy="true"
          aria-label="Loading definition…"
        >
          <SkeletonBone size="block" height="8rem" />
        </div>
      ) : null}
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {data?.eligible && data.yaml !== null ? (
        <pre
          className="service-definition-yaml"
          tabIndex={0}
          dangerouslySetInnerHTML={{
            __html: highlighter.highlightHtml(data.yaml),
          }}
        />
      ) : null}
    </section>
  );
}
