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
  display?: string;
  group_by?: string;
  lanes?: string[];
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
  const error = validateQuery(data as Record<string, unknown>);
  if (error) return { query: null, error };
  return { query: data, error: "" };
}

function validateQuery(query: Record<string, unknown>): string {
  const display = query["display"];
  if (display !== undefined && display !== "table" && display !== "kanban") {
    return `display must be "table" or "kanban", got: ${formatValue(display)}`;
  }
  if (display === "kanban" && typeof query["group_by"] !== "string") {
    return "kanban display requires group_by";
  }
  const lanes = query["lanes"];
  if (lanes !== undefined) {
    const list: unknown[] = Array.isArray(lanes) ? lanes : [lanes];
    const nonScalar = list.find((lane) => lane === null || typeof lane === "object");
    if (nonScalar !== undefined) return "lanes entries must be scalar values";
  }
  return "";
}

function compareValues(a: unknown, b: unknown): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return formatValue(a).localeCompare(formatValue(b));
}

function sortRows(entries: FrontmatterEntry[], sortSpec: string | undefined): FrontmatterEntry[] {
  const rows = [...entries];
  if (!sortSpec) return rows.sort((x, y) => x.path.localeCompare(y.path));

  const desc = sortSpec.startsWith("-");
  const field = desc ? sortSpec.slice(1) : sortSpec;
  rows.sort((x, y) => {
    const xMissing = !(field in x.frontmatter) || x.frontmatter[field] === null;
    const yMissing = !(field in y.frontmatter) || y.frontmatter[field] === null;
    // Entries missing the sort field always sink to the bottom, even for descending sorts.
    if (xMissing || yMissing) {
      if (xMissing && yMissing) return x.path.localeCompare(y.path);
      return xMissing ? 1 : -1;
    }
    const cmp = compareValues(x.frontmatter[field], y.frontmatter[field]);
    if (cmp !== 0) return desc ? -cmp : cmp;
    return x.path.localeCompare(y.path);
  });
  return rows;
}

function basename(path: string): string {
  return path.split("/").pop() || path;
}

interface Lane {
  label: string;
  rows: FrontmatterEntry[];
}

function groupLanes(rows: FrontmatterEntry[], groupBy: string, lanes?: string[]): Lane[] {
  const byKey = new Map<string, FrontmatterEntry[]>();
  const missing: FrontmatterEntry[] = [];
  for (const row of rows) {
    const value = row.frontmatter[groupBy];
    if (value === null || value === undefined) {
      missing.push(row);
      continue;
    }
    const key = formatValue(value);
    const bucket = byKey.get(key);
    if (bucket) bucket.push(row);
    else byKey.set(key, [row]);
  }

  const ordered = (lanes ?? [...byKey.keys()]).map(String);
  const listed = new Set(ordered);
  const result = ordered.map((label) => ({ label, rows: byKey.get(label) ?? [] }));

  const other = [...byKey.entries()]
    .filter(([key]) => !listed.has(key))
    .flatMap(([, laneRows]) => laneRows);
  if (other.length > 0) result.push({ label: "Other", rows: other });
  if (missing.length > 0) result.push({ label: `No ${groupBy}`, rows: missing });
  return result;
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
  return <ViewDisplay query={query} workspaceId={ctx.workspaceId} onFileClick={ctx.onFileClick} />;
}

function ViewDisplay({ query, workspaceId, onFileClick }: { query: string } & ViewContextValue) {
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

  const groupBy = parsed.query?.group_by;
  const kanban = parsed.query?.display === "kanban" && groupBy ? groupBy : undefined;

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
      <div className="mb-4 flex justify-center py-6 text-xs text-foreground/70 uppercase tracking-widest">
        Querying workspace...
      </div>
    );
  }

  return (
    <div className="mb-4 cp-cut-6 border border-cp-border bg-cp-surface3">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border">
        <span className="cp-label text-foreground/70" style={{ fontSize: "10px" }}>
          View · {rows.length} {rows.length === 1 ? "file" : "files"}
        </span>
        {/* Agent edits to other workspace files don't re-render an open view; manual refresh is the v1 answer. */}
        <button
          className="text-foreground/70 hover:text-foreground"
          title="Refresh"
          onClick={() => setRefreshTick((t) => t + 1)}
        >
          <RefreshCw className="h-3 w-3" />
        </button>
      </div>
      {rows.length === 0 ? (
        <div className="px-3 py-6 text-center cp-label opacity-60 italic">No files match</div>
      ) : kanban ? (
        <KanbanView
          rows={rows}
          groupBy={kanban}
          lanes={parsed.query?.lanes}
          onFileClick={onFileClick}
        />
      ) : (
        <TableView
          rows={rows}
          columns={parsed.query?.columns}
          onFileClick={onFileClick}
        />
      )}
    </div>
  );
}

function TableView({
  rows,
  columns: specified,
  onFileClick,
}: {
  rows: FrontmatterEntry[];
  columns?: string[];
  onFileClick: (path: string) => void;
}) {
  const columns = useMemo(() => {
    if (typeof specified === "string") return [specified];
    if (Array.isArray(specified) && specified.length > 0) return specified;

    const seen: string[] = [];
    for (const entry of rows) {
      for (const key of Object.keys(entry.frontmatter)) {
        if (!seen.includes(key)) seen.push(key);
      }
    }
    return seen;
  }, [rows, specified]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse border border-cp-border">
        <thead className="bg-foreground/5">
          <tr>
            <th className="px-3 py-2 text-left text-sm font-bold text-foreground border border-border">
              File
            </th>
            {columns.map((column) => (
              <th
                key={column}
                className="px-3 py-2 text-left text-sm font-bold text-foreground border border-border"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((entry) => (
            <tr key={entry.path} className="even:bg-foreground/5">
              <td className="px-3 py-2 text-sm border border-border">
                <a
                  href="#"
                  className="text-cp-cyan underline decoration-cp-cyan/40 hover:decoration-cp-cyan"
                  title={entry.path}
                  onClick={(e) => {
                    e.preventDefault();
                    onFileClick(entry.path);
                  }}
                >
                  {dirname(entry.path) && (
                    <span className="text-foreground">
                      {dirname(entry.path)}/
                    </span>
                  )}
                  {basename(entry.path)}
                </a>
              </td>
              {columns.map((column) => (
                <td
                  key={column}
                  className="px-3 py-2 text-sm text-foreground/90 font-mono border border-border"
                >
                  {column in entry.frontmatter ? (
                    formatValue(entry.frontmatter[column])
                  ) : (
                    <span className="text-foreground/40">—</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function KanbanView({
  rows,
  groupBy,
  lanes,
  onFileClick,
}: {
  rows: FrontmatterEntry[];
  groupBy: string;
  lanes?: string[];
  onFileClick: (path: string) => void;
}) {
  const laneList = typeof lanes === "string" ? [lanes] : lanes;
  const laneData = groupLanes(rows, groupBy, laneList);

  return (
    <div className="overflow-x-auto p-3 flex gap-4 items-start">
      {laneData.map((lane) => (
        <div key={lane.label} data-lane={lane.label} className="w-56 shrink-0">
          <div className="cp-label mb-2 px-1 flex items-baseline gap-1.5">
            <span className="text-cp-yellow">{lane.label}</span>
            <span className="text-foreground/60">· {lane.rows.length}</span>
          </div>
          <div className="flex flex-col gap-2">
            {lane.rows.map((entry) => (
              <div
                key={entry.path}
                className="cp-cut-6 cp-hover-user border bg-cp-surface2 px-2.5 py-2"
              >
                <a
                  href="#"
                  className="text-sm text-cp-cyan underline decoration-cp-cyan/40 hover:decoration-cp-cyan"
                  title={entry.path}
                  onClick={(e) => {
                    e.preventDefault();
                    onFileClick(entry.path);
                  }}
                >
                  {basename(entry.path)}
                </a>
                {dirname(entry.path) && (
                  <div className="text-xs font-mono text-foreground">
                    {dirname(entry.path)}/
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
