import { parse } from "yaml";

export interface FrontmatterData {
  metadata: Record<string, unknown>;
  content: string;
}

const FRONTMATTER_RE = /^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n/;

export function parseFrontmatter(raw: string): FrontmatterData | null {
  const match = raw.match(FRONTMATTER_RE);
  if (!match) return null;

  let metadata: unknown;
  try {
    metadata = parse(match[1]);
  } catch {
    return null;
  }

  if (typeof metadata !== "object" || metadata === null || Array.isArray(metadata)) {
    return null;
  }

  const record = metadata as Record<string, unknown>;
  if (Object.keys(record).length === 0) return null;

  return {
    metadata: record,
    content: raw.slice(match[0].length),
  };
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "bigint") {
    return value.toString();
  }
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (typeof value === "symbol" || typeof value === "function") {
    return value.toString();
  }
  return JSON.stringify(value);
}
