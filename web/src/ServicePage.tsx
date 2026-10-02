import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  documentTitleForHost,
  fetchMetrics,
  fetchService,
  type MetricsSeries,
  type ServiceDetailPayload,
} from "./api";
import {
  invalidateMetrics,
  invalidateStatus,
  refreshStatus,
} from "./dashboardCache";
import { ServiceDetail } from "./ServiceDetail";

/** Deep-linked service page: `/service/:service`. */
export function ServicePage() {
  const { service: raw } = useParams<{ service: string }>();
  const service = raw ? decodeURIComponent(raw) : "";
  const [data, setData] = useState<ServiceDetailPayload | null>(null);
  const [metrics, setMetrics] = useState<MetricsSeries | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  const load = useCallback(async () => {
    if (!service) {
      setError("Missing service name.");
      setBusy(false);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const detail = await fetchService(service);
      setData(detail);
      setMetrics(await loadServiceMetrics(service));
    } catch (err) {
      setData(null);
      setMetrics(null);
      setError(err instanceof Error && err.message === "not found"
        ? `Service '${service}' was not found in the current status snapshot.`
        : "Failed to load service detail.");
    } finally {
      setBusy(false);
    }
  }, [service]);

  useEffect(() => {
    void load();
  }, [load]);

  const onActionDone = useCallback(async () => {
    await load();
    try {
      await refreshStatus();
    } catch {
      invalidateStatus();
    }
    invalidateMetrics();
  }, [load]);

  useEffect(() => {
    const label = data?.presentation.name ?? service;
    document.title = label
      ? `raft - ${label}`
      : documentTitleForHost(data?.host?.hostname);
  }, [data, service]);

  return (
    <div className="page">
      <header className="header">
        <div>
          <p className="brand">raft</p>
          <h1>{(data?.presentation.name ?? service) || "Service"}</h1>
        </div>
        <Link className="back-link" to="/">
          ← Back to status
        </Link>
      </header>

      {busy && data === null && !error ? (
        <div className="loading" role="status" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <p>Loading service…</p>
        </div>
      ) : null}

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      {data ? (
        <ServiceDetail
          data={data}
          metrics={metrics}
          onActionDone={() => void onActionDone()}
        />
      ) : null}
    </div>
  );
}

async function loadServiceMetrics(service: string): Promise<MetricsSeries | null> {
  try {
    const payload = await fetchMetrics({ window: 3600, services: [service] });
    return payload.series.find((s) => s.id === service) ?? null;
  } catch {
    return null;
  }
}
