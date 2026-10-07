import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { parse } from "yaml";
import { RefreshCw } from "lucide-react";
import { api, type FrontmatterEntry } from "../lib/api.ts";
import { formatValue } from "../lib/frontmatter.ts";
import { CodeBlock } from "../lib/code-block.tsx";

interface ViewContextValue {
  workspaceId: string;
  onFileClick: (path: string) => void;
}

export const ViewBlockContext = createContext<ViewContextValue | null>(null);

interface ViewQuery {
  glob?: string;
  columns?: string[];
  sort?: string;
}

function parseQuery(query: string): { query: ViewQuery | null; error: string } {
  let data: unknown;
  try {
    // Globs like `**/*.md` read as YAML aliases (unresolved-anchor errors);
    // quote any plain value starting with `*` so it parses as a string.
    const quoted = query.replace(
      /^(\s*[^\s:#][^:]*:\s*)(\*.+)$/gm,
      (_m, key: string, value: string) => `${key}${JSON.stringify(value)}`
    );
    data = parse(quoted);
  } catch (e) {
    return { query: null, error: e instanceof Error ? e.message : String(e) };
  }
  if (data === null) return { query: {}, error: "" };
  if (typeof data !== "object" || Array.isArray(data)) {
    return { query: null, error: "View query must be a YAML mapping" };
  }
  return { query: data, error: "" };
}

function compareValues(a: unknown, b: unknown): number {
  const aMissing = a === null || a === undefined;
  const bMissing = b === null || b === undefined;
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return formatValue(a).localeCompare(formatValue(b));
}

function sortRows(entries: FrontmatterEntry[], sortSpec: string | undefined): FrontmatterEntry[] {
  const rows = [...entries];
  if (!sortSpec) return rows.sort((x, y) => x.path.localeCompare(y.path));

  const desc = sortSpec.startsWith("-");
  const field = desc ? sortSpec.slice(1) : sortSpec;
  rows.sort((x, y) => {
    const cmp = compareValues(x.frontmatter[field], y.frontmatter[field]);
    if (cmp !== 0) return desc ? -cmp : cmp;
    return x.path.localeCompare(y.path);
  });
  return rows;
}

function basename(path: string): string {
  return path.split("/").pop() || path;
}

function dirname(path: string): string {
  const parts = path.split("/");
  parts.pop();
  return parts.join("/");
}

export function ViewBlock({ query }: { query: string }) {
  const ctx = useContext(ViewBlockContext);
  if (!ctx) {
    return <CodeBlock code={query} lang="view" />;
  }
  return <ViewTable query={query} workspaceId={ctx.workspaceId} onFileClick={ctx.onFileClick} />;
}

function ViewTable({ query, workspaceId, onFileClick }: { query: string } & ViewContextValue) {
  const [entries, setEntries] = useState<FrontmatterEntry[] | null>(null);
  const [fetchError, setFetchError] = useState("");
  const [refreshTick, setRefreshTick] = useState(0);

  const parsed = useMemo(() => parseQuery(query), [query]);
  const glob = parsed.query?.glob ?? "**/*";

  useEffect(() => {
    if (parsed.error) return;

    let cancelled = false;
    api.getWorkspaceFrontmatter(workspaceId, glob)
      .then((files) => {
        if (cancelled) return;
        setEntries(files);
        setFetchError("");
      })
      .catch((e) => {
        if (cancelled) return;
        setFetchError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, glob, parsed.error, refreshTick]);

  const rows = useMemo(
    () => sortRows(entries ?? [], parsed.query?.sort),
    [entries, parsed.query?.sort]
  );

  const columns = useMemo(() => {
    const specified = parsed.query?.columns;
    if (typeof specified === "string") return [specified];
    if (Array.isArray(specified) && specified.length > 0) return specified;

    const seen: string[] = [];
    for (const entry of rows) {
      for (const key of Object.keys(entry.frontmatter)) {
        if (!seen.includes(key)) seen.push(key);
      }
    }
    return seen;
  }, [rows, parsed.query?.columns]);

  if (parsed.error) {
    return (
      <pre className="overflow-x-auto mb-4 p-3 text-xs text-[var(--color-cp-red)] bg-cp-surface2 border border-[var(--color-cp-red)]/30">
        <code>{parsed.error}</code>
      </pre>
    );
  }

  if (fetchError) {
    return (
      <pre className="overflow-x-auto mb-4 p-3 text-xs text-[var(--color-cp-red)] bg-cp-surface2 border border-[var(--color-cp-red)]/30">
        <code>{fetchError}</code>
      </pre>
    );
  }

  if (entries === null) {
    return (
      <div className="mb-4 flex justify-center py-6 text-xs text-[var(--color-cp-text-muted)] uppercase tracking-widest">
        Querying workspace...
      </div>
    );
  }

  return (
    <div
      className="mb-4 cp-cut-6 border"
      style={{
        borderColor: "rgb(var(--cp-rgb-yellow) / 0.15)",
        background: "rgb(var(--cp-rgb-yellow) / 0.03)",
      }}
    >
      <div
        className="flex items-center justify-between px-3 py-1.5 border-b"
        style={{ borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)" }}
      >
        <span className="cp-label text-primary/50" style={{ fontSize: "10px" }}>
          View · {rows.length} {rows.length === 1 ? "file" : "files"}
        </span>
        {/* Agent edits to other workspace files don't re-render an open view; manual refresh is the v1 answer. */}
        <button
          className="text-primary/50 hover:text-primary"
          title="Refresh"
          onClick={() => setRefreshTick((t) => t + 1)}
        >
          <RefreshCw className="h-3 w-3" />
        </button>
      </div>
      {rows.length === 0 ? (
        <div className="px-3 py-6 text-center cp-label opacity-40 italic">No files match</div>
      ) : (
        <div className="overflow-x-auto">
          <table
            className="w-full border-collapse border"
            style={{ borderColor: "rgb(var(--cp-rgb-yellow) / 0.2)" }}
          >
            <thead style={{ backgroundColor: "rgb(var(--cp-rgb-yellow) / 0.06)" }}>
              <tr>
                <th
                  className="px-3 py-2 text-left text-sm font-bold text-foreground"
                  style={{ borderWidth: "1px", borderStyle: "solid", borderColor: "rgb(var(--cp-rgb-yellow) / 0.2)" }}
                >
                  File
                </th>
                {columns.map((column) => (
                  <th
                    key={column}
                    className="px-3 py-2 text-left text-sm font-bold text-foreground"
                    style={{ borderWidth: "1px", borderStyle: "solid", borderColor: "rgb(var(--cp-rgb-yellow) / 0.2)" }}
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((entry) => (
                <tr key={entry.path} className="even:bg-primary/3">
                  <td
                    className="px-3 py-2 text-sm"
                    style={{ borderWidth: "1px", borderStyle: "solid", borderColor: "rgb(var(--cp-rgb-yellow) / 0.15)" }}
                  >
                    <a
                      href="#"
                      className="text-primary underline decoration-primary/40 hover:decoration-primary"
                      title={entry.path}
                      onClick={(e) => {
                        e.preventDefault();
                        onFileClick(entry.path);
                      }}
                    >
                      {dirname(entry.path) && (
                        <span className="text-[var(--color-cp-text-muted)]">
                          {dirname(entry.path)}/
                        </span>
                      )}
                      {basename(entry.path)}
                    </a>
                  </td>
                  {columns.map((column) => (
                    <td
                      key={column}
                      className="px-3 py-2 text-sm text-foreground/80 font-mono"
                      style={{ borderWidth: "1px", borderStyle: "solid", borderColor: "rgb(var(--cp-rgb-yellow) / 0.15)" }}
                    >
                      {column in entry.frontmatter ? (
                        formatValue(entry.frontmatter[column])
                      ) : (
                        <span className="text-foreground/25">—</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
