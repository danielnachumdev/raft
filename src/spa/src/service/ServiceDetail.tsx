import { useState } from "react";
import type { ServiceDetailPayload } from "../shared/api";
import { ServiceLogs } from "../logs/ServiceLogs";
import { ServiceTrendsDashboard } from "../trends/service/ui/ServiceTrendsDashboard";
import { ServiceHttpRequests } from "./httpRequests/ServiceHttpRequests";
import { ServiceDefinition } from "./ServiceDefinition";
import { ServiceDetailsPanel } from "./ServiceDetailsPanel";
import { ServiceOverview } from "./ServiceOverview";
import { ServiceSectionNav, type ServiceSection } from "./ServiceSectionNav";
import "./ServiceDetail.css";

/** Service page body: overview → logs → trends → HTTP → definition → details. */
export function ServiceDetail(props: { data: ServiceDetailPayload }) {
  const { container: c, presentation: p } = props.data;
  // Host-routed Apps (external URLs) keep the HTTP nav even when scaled to
  // zero / stopped — history comes from the gate access log, not the container.
  const hostRouted = (p.external_urls?.length ?? 0) > 0;
  const isApp = c.role === "app";
  const [httpEligible, setHttpEligible] = useState(hostRouted);
  const showHttp = hostRouted || httpEligible;
  const sections: ServiceSection[] = [
    { id: "overview", label: "Overview" },
    { id: "logs", label: "Logs" },
    { id: "trends", label: "Trends" },
    ...(showHttp ? [{ id: "http", label: "HTTP requests" }] : []),
    ...(isApp ? [{ id: "definition", label: "Definition" }] : []),
    { id: "details", label: "Details" },
  ];
  return (
    <>
      <ServiceSectionNav sections={sections} />
      <div className="service-section" id="overview">
        <ServiceOverview data={props.data} />
      </div>
      <div className="service-section" id="logs">
        <ServiceLogs
          service={c.service}
          running={/running|up|healthy/i.test(c.status)}
        />
      </div>
      <div className="service-section" id="trends">
        <ServiceTrendsDashboard service={c.service} />
      </div>
      <div className="service-section" id="http">
        <ServiceHttpRequests
          service={c.service}
          appName={c.app}
          containerStatus={c.status}
          onEligibleChange={setHttpEligible}
        />
      </div>
      {isApp ? (
        <div className="service-section" id="definition">
          <ServiceDefinition service={c.service} />
        </div>
      ) : null}
      <div className="service-section" id="details">
        <ServiceDetailsPanel data={props.data} />
      </div>
    </>
  );
}
