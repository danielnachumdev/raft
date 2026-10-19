/** Eager public surface for the typed `/api` client. */

export {
  detailFromBody,
  readJsonBody,
} from "./http.ts";
export {
  STATUS_POLL_MS,
  documentTitleForHost,
  fetchStatus,
  serviceLogsPath,
  servicePath,
  type RaftVersion,
  type RegistryIssue,
  type StatusPayload,
  type StatusRow,
} from "./status.ts";
export {
  fetchService,
  postPurge,
  postServiceAction,
  type ContainerDetail,
  type PurgeResult,
  type ServiceAction,
  type ServiceActionResult,
  type ServiceDetailPayload,
} from "./service.ts";
export {
  DEFAULT_LOG_TAIL,
  fetchServiceLogs,
  openServiceLogsFollow,
  serviceLogsFollowUrl,
  type ServiceLogsPayload,
} from "./logs.ts";
export {
  METRICS_POLL_MS,
  fetchHttpMetrics,
  fetchMetrics,
  type GraphEvent,
  type MetricsAvailable,
  type MetricsBounds,
  type MetricsPayload,
  type MetricsPoint,
  type MetricsQuery,
  type MetricsSeries,
} from "./metrics.ts";
export {
  DEFAULT_HTTP_REQUESTS_LIMIT,
  HTTP_REQUESTS_POLL_MS,
  fetchServiceHttpRequests,
  type HttpRequestRow,
  type HttpRequestsPayload,
} from "./httpRequests.ts";
