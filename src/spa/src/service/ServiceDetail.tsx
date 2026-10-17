import { useState } from "react";
import type { ServiceDetailPayload } from "../shared/api";
import { ServiceLogs } from "../logs/ServiceLogs";
import { ServiceTrendsDashboard } from "../trends/service/ui/ServiceTrendsDashboard";
import { ServiceHttpRequests } from "./httpRequests/ServiceHttpRequests";
import { ServiceDetailsPanel } from "./ServiceDetailsPanel";
import { ServiceOverview } from "./ServiceOverview";
import { ServiceSectionNav, type ServiceSection } from "./ServiceSectionNav";
import "./ServiceDetail.css";

/** Service page body: overview → logs → trends → HTTP → details. */
export function ServiceDetail(props: { data: ServiceDetailPayload }) {
  const { container: c } = props.data;
  const [httpEligible, setHttpEligible] = useState(false);
  const sections: ServiceSection[] = [
    { id: "overview", label: "Overview" },
    { id: "logs", label: "Logs" },
    { id: "trends", label: "Trends" },
    ...(httpEligible ? [{ id: "http", label: "HTTP requests" }] : []),
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
      <div className="service-section" id="details">
        <ServiceDetailsPanel data={props.data} />
      </div>
    </>
  );
}
