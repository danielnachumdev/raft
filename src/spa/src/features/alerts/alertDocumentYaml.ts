/** Minimal YAML dump for alert rule documents (no third-party parser). */

export function alertDocumentJson(doc: unknown): string {
  return `${JSON.stringify(doc, null, 2)}\n`;
}

/** Serialize a JSON-compatible value to indented YAML. */
export function alertDocumentYaml(value: unknown, indent = 0): string {
  return `${dumpValue(value, indent).replace(/\s+$/, "")}\n`;
}

function dumpValue(value: unknown, indent: number): string {
  if (value === null) return "null";
  if (typeof value === "boolean" || typeof value === "number") return String(value);
  if (typeof value === "string") return dumpString(value);
  if (Array.isArray(value)) return dumpArray(value, indent);
  if (value && typeof value === "object") {
    return dumpObject(value as Record<string, unknown>, indent);
  }
  return dumpString(String(value));
}

function dumpObject(obj: Record<string, unknown>, indent: number): string {
  const keys = Object.keys(obj);
  if (!keys.length) return "{}";
  const pad = "  ".repeat(indent);
  return keys
    .map((key) => {
      const child = obj[key];
      if (isPlainObject(child) || Array.isArray(child)) {
        if (isEmptyCollection(child)) {
          return `${pad}${key}: ${dumpValue(child, 0)}`;
        }
        return `${pad}${key}:\n${dumpValue(child, indent + 1)}`;
      }
      return `${pad}${key}: ${dumpValue(child, indent + 1)}`;
    })
    .join("\n");
}

function dumpArray(items: unknown[], indent: number): string {
  if (!items.length) return "[]";
  const pad = "  ".repeat(indent);
  return items
    .map((item) => {
      if (isPlainObject(item)) {
        const body = dumpObject(item as Record<string, unknown>, indent + 1);
        const lines = body.split("\n");
        const first = lines[0]?.replace(/^\s+/, "") ?? "";
        const rest = lines.slice(1).join("\n");
        return rest ? `${pad}- ${first}\n${rest}` : `${pad}- ${first}`;
      }
      if (Array.isArray(item)) {
        return `${pad}-\n${dumpValue(item, indent + 1)}`;
      }
      return `${pad}- ${dumpValue(item, indent + 1)}`;
    })
    .join("\n");
}

function dumpString(value: string): string {
  if (value === "") return '""';
  if (/^[\w./:@*+-]+$/.test(value) && !/^(true|false|null)$/i.test(value)) {
    return value;
  }
  return JSON.stringify(value);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function isEmptyCollection(value: unknown): boolean {
  if (Array.isArray(value)) return value.length === 0;
  if (isPlainObject(value)) return Object.keys(value).length === 0;
  return false;
}
