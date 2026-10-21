/** Per-service detail + lifecycle actions + purge. */

import {
  appResourceCache,
  resourceId,
} from "../cache/index.ts";
import { detailFromBody, readJsonBody } from "./http.ts";
import type { StatusRow } from "./status.ts";

export type ContainerDetail = {
  service: string;
  role: string;
  app: string | null;
  group: string | null;
  status: string;
  uptime_seconds: number | null;
  cpu_percent: number | null;
  memory: {
    used_bytes: number | null;
    limit_bytes: number | null;
    used_percent: number | null;
  };
  allocated: {
    cpus_limit: string;
    memory_limit: string;
    cpus_reservation: string;
    memory_reservation: string;
  };
  network: { rx_bytes: number | null; tx_bytes: number | null };
  block_io: { read_bytes: number | null; write_bytes: number | null };
  pids: number | null;
};

export type ServiceDetailPayload = {
  host: { hostname?: string; [key: string]: unknown };
  container: ContainerDetail;
  presentation: StatusRow;
};

export type ServiceAction = "start" | "stop" | "redeploy";

export type ServiceActionResult = {
  ok: boolean;
  action: ServiceAction;
  service: string;
  /** Present when always-on dashboard enqueued a detached host one-shot. */
  started?: boolean;
  job_id?: string;
};

export type PurgeResult = {
  ok: boolean;
  action: "purge";
  reclaimed_bytes: number;
  reclaimed_human: string;
  images_bytes: number;
  builder_bytes: number;
};

function serviceResourceId(name: string) {
  return resourceId("service", name);
}

async function loadService(name: string): Promise<ServiceDetailPayload> {
  const res = await fetch(`/api/service/${encodeURIComponent(name)}`);
  if (res.status === 404) {
    throw new Error("not found");
  }
  if (!res.ok) {
    throw new Error(`service ${res.status}`);
  }
  return (await res.json()) as ServiceDetailPayload;
}

export async function fetchService(name: string): Promise<ServiceDetailPayload> {
  return appResourceCache.readThrough(serviceResourceId(name), {
    read: () => loadService(name),
  });
}

export async function postServiceAction(
  name: string,
  action: ServiceAction,
): Promise<ServiceActionResult> {
  const res = await fetch(
    `/api/service/${encodeURIComponent(name)}/${action}`,
    { method: "POST" },
  );
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `${action} failed (${res.status})`);
  }
  appResourceCache.invalidate(serviceResourceId(name));
  return body as ServiceActionResult;
}

export async function postPurge(): Promise<PurgeResult> {
  const res = await fetch("/api/purge", { method: "POST" });
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `purge failed (${res.status})`);
  }
  appResourceCache.invalidateNamespace("service");
  return body as PurgeResult;
}
