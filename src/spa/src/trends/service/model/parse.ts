import { parseGraph } from "../../dashboard/model/parse.ts";
import type { TrendsGraphConfig } from "../../dashboard/model/types.ts";
import { parseRange } from "../../range/validate.ts";
import type { ServiceTrendsLayout, ServiceTrendsStore } from "./types.ts";

/** Validate a stored v1 payload; null when it is not a usable store. */
export function parseServiceTrendsStore(
  raw: unknown,
): ServiceTrendsStore | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (obj.version !== 1 || !obj.services || typeof obj.services !== "object") {
    return null;
  }
  const services: Record<string, ServiceTrendsLayout> = {};
  for (const [name, layout] of Object.entries(
    obj.services as Record<string, unknown>,
  )) {
    if (!name.trim()) continue;
    const parsed = parseServiceLayout(layout);
    if (parsed) services[name] = parsed;
  }
  return { version: 1, services };
}

export function parseServiceLayout(raw: unknown): ServiceTrendsLayout | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (typeof obj.updatedAt !== "string" || !Array.isArray(obj.panels)) {
    return null;
  }
  const range = parseRange(obj.range);
  if (!range) return null;
  const panels = uniqueById(
    obj.panels
      .map(parseGraph)
      .filter((p): p is TrendsGraphConfig => p !== null),
  );
  return { updatedAt: obj.updatedAt, range, panels };
}

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}
