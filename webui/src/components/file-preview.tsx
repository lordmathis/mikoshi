import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeMathjax from "rehype-mathjax";
import "highlight.js/styles/github-dark.css";
import { Loader2, X, File } from "lucide-react";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { remarkWikiLinks, resolveTarget } from "../lib/remark-wiki-links";
import { markdownComponents, REMARK_PLUGINS, REHYPE_PLUGINS } from "../lib/markdown-components";

interface FilePreviewProps {
  filePath: string | null;
  fileContent: string | null;
  isLoading: boolean;
  onClose: () => void;
  workspaceId: string | null;
  fileIndex: Map<string, string>;
  onFileClick: (path: string) => void;
  hideHeader?: boolean;
}

function isMarkdownFile(path: string): boolean {
  return /\.(md|mdx|markdown)$/i.test(path);
}

interface FrontmatterData {
  metadata: Record<string, unknown>;
  content: string;
}

const FRONTMATTER_RE = /^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n/;

function parseFrontmatter(raw: string): FrontmatterData | null {
  const match = raw.match(FRONTMATTER_RE);
  if (!match) return null;

  const yaml = match[1].trim();
  if (!yaml) return null;

  const metadata: Record<string, unknown> = {};
  const lines = yaml.split(/\r?\n/);
  let currentKey: string | null = null;
  const currentArray: unknown[] = [];

  function flushArray() {
    if (currentKey !== null && currentArray.length > 0) {
      metadata[currentKey] = currentArray.slice();
      currentArray.length = 0;
    }
  }

  for (const line of lines) {
    const arrayItem = line.match(/^\s+-\s+(.*)/);
    if (arrayItem) {
      if (currentKey !== null) {
        currentArray.push(parseValue(arrayItem[1]));
      }
      continue;
    }

    const kv = line.match(/^([\w.-]+)\s*:\s*(.*)/);
    if (kv) {
      flushArray();
      currentKey = kv[1];
      const val = kv[2].trim();
      if (val === "") {
        currentArray.length = 0;
      } else {
        metadata[currentKey] = parseValue(val);
        currentKey = null;
      }
      continue;
    }

    if (currentKey !== null && line.trim() !== "") {
      const existing = metadata[currentKey];
      if (typeof existing === "string") {
        metadata[currentKey] = existing + "\n" + line.trim();
      }
    }
  }

  flushArray();

  if (Object.keys(metadata).length === 0) return null;

  return {
    metadata,
    content: raw.slice(match[0].length),
  };
}

function parseValue(val: string): unknown {
  if (val === "true") return true;
  if (val === "false") return false;
  if (val === "null" || val === "~") return null;
  if (/^-?\d+$/.test(val)) return parseInt(val, 10);
  if (/^-?\d+\.\d+$/.test(val)) return parseFloat(val);
  if (/^(["'])(.*)\1$/.test(val)) return val.slice(1, -1);
  if (/^\[.*\]$/.test(val)) {
    try {
      return JSON.parse(val);
    } catch {
      return val;
    }
  }
  return val;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function FrontmatterPanel({ metadata }: { metadata: Record<string, unknown> }) {
  const entries = Object.entries(metadata);
  if (entries.length === 0) return null;

  return (
    <div
      className="mb-5 cp-cut-6 border"
      style={{
        borderColor: "rgb(var(--cp-rgb-yellow) / 0.15)",
        background: "rgb(var(--cp-rgb-yellow) / 0.03)",
      }}
    >
      <div
        className="px-3 py-1.5 border-b flex items-center gap-1.5"
        style={{ borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)" }}
      >
        <span
          className="inline-block w-1.5 h-1.5"
          style={{ background: "var(--color-cp-yellow)", opacity: 0.6 }}
        />
        <span className="cp-label text-primary/50" style={{ fontSize: "10px" }}>
          Metadata
        </span>
      </div>
      <div className="px-3 py-2 space-y-1">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-baseline gap-2 text-sm">
            <span
              className="shrink-0 font-mono text-primary/70"
              style={{ fontSize: "12px" }}
            >
              {key}
            </span>
            <span className="text-foreground/25">:</span>
            <span className="text-foreground/60 font-mono break-all" style={{ fontSize: "12px" }}>
              {formatValue(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FilePreview({ filePath, fileContent, isLoading, onClose, workspaceId, fileIndex, onFileClick, hideHeader }: FilePreviewProps) {
  if (!filePath) return null;

  const fileName = filePath.split("/").pop() || filePath;
  const isMd = isMarkdownFile(filePath);

  const remarkPlugins: any[] = [...REMARK_PLUGINS, remarkMath, remarkWikiLinks];

  const components: Record<string, React.ComponentType<any>> = {
    ...markdownComponents,
    img: ({ src, alt }: any) => {
      if (!src) return null;
      if (!src.startsWith("http") && !src.startsWith("data:")) {
        const dir = filePath?.includes("/") ? filePath.substring(0, filePath.lastIndexOf("/") + 1) : "";
        src = `/api/workspaces/${workspaceId}/files/${dir}${src}`;
      }
      return <img src={src} alt={alt} className="max-w-full h-auto rounded" />;
    },
    a: ({ href, children }: any) => {
      if (href?.startsWith("wiki-image://")) {
        const target = decodeURIComponent(href.replace("wiki-image://", ""));
        const resolved = workspaceId ? resolveTarget(target, fileIndex) : null;
        if (resolved) {
          return <img src={`/api/workspaces/${workspaceId}/files/${resolved}`} alt={target} className="max-w-full h-auto rounded" />;
        }
        return (
          <span
            style={{ color: "rgb(var(--cp-rgb-yellow) / 0.5)", background: "rgb(var(--cp-rgb-yellow) / 0.06)", padding: "0 3px", borderRadius: "3px", fontSize: "0.9em" }}
          >
            {`![[${target}]]`}
          </span>
        );
      }
      if (href?.startsWith("wiki://")) {
        const target = decodeURIComponent(href.replace("wiki://", ""));
        const resolved = workspaceId ? resolveTarget(target, fileIndex) : null;
        if (resolved) {
          return (
            <a
              href="#"
              className="text-primary underline decoration-primary/40 hover:decoration-primary"
              onClick={(e) => { e.preventDefault(); onFileClick(resolved); }}
            >
              {children}
            </a>
          );
        }
        return (
          <span
            style={{ color: "rgb(var(--cp-rgb-yellow) / 0.5)", background: "rgb(var(--cp-rgb-yellow) / 0.06)", padding: "0 3px", borderRadius: "3px", fontSize: "0.9em" }}
          >
            {`[[${target}]]`}
          </span>
        );
      }
      return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
    },
  };

  return (
    <div className={hideHeader ? "flex flex-col flex-1 min-h-0" : "flex flex-col h-full overflow-hidden border-r"} style={hideHeader ? undefined : { borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)" }}>
      {!hideHeader && (
        <div
          className="flex items-center justify-between px-4 py-2 shrink-0 border-b"
          style={{
            borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)",
            background: "rgb(var(--cp-rgb-surface3) / 0.95)",
          }}
        >
          <div className="flex items-center gap-2 min-w-0">
            <File className="h-4 w-4 text-primary/60 flex-shrink-0" />
            <span className="cp-label text-foreground truncate">{fileName}</span>
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7 opacity-50 hover:opacity-100" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-primary/50" />
            </div>
          ) : fileContent === null ? (
            <div className="py-12 text-center cp-label opacity-20 italic">
              Failed to load file
            </div>
          ) : isMd ? (
            <div className="text-foreground/90 font-sans" style={{ lineHeight: '1.6' }}>
              {(() => {
                const parsed = parseFrontmatter(fileContent);
                const mdContent = parsed ? parsed.content : fileContent;
                return (
                  <>
                    {parsed && <FrontmatterPanel metadata={parsed.metadata} />}
                    <ReactMarkdown
                      remarkPlugins={remarkPlugins}
                      rehypePlugins={[...REHYPE_PLUGINS, rehypeMathjax]}
                      components={components}
                      urlTransform={(url) => {
                        if (url.startsWith("wiki://") || url.startsWith("wiki-image://")) return url;
                        return url;
                      }}
                    >
                      {mdContent}
                    </ReactMarkdown>
                  </>
                );
              })()}
            </div>
          ) : (
            <pre className="text-sm text-foreground/80 whitespace-pre-wrap break-words font-mono">
              {fileContent}
            </pre>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
