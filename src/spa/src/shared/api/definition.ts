/** Applied App manifest YAML for service diagnostics. */

export type ServiceDefinitionPayload = {
  service: string;
  app: string | null;
  path: string | null;
  yaml: string | null;
  eligible: boolean;
  reason: string | null;
  unknown?: boolean;
};

export async function fetchServiceDefinition(
  name: string,
): Promise<ServiceDefinitionPayload> {
  const res = await fetch(
    `/api/service/${encodeURIComponent(name)}/definition`,
  );
  if (res.status === 404) {
    throw new Error("not found");
  }
  if (!res.ok) {
    throw new Error(`definition ${res.status}`);
  }
  return (await res.json()) as ServiceDefinitionPayload;
}
