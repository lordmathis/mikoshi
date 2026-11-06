import type { ComponentProps } from "react";
import ReactMarkdown, { defaultUrlTransform, type Components, type ExtraProps } from "react-markdown";
import type { PluggableList } from "unified";
import remarkMath from "remark-math";
import rehypeMathjax from "rehype-mathjax";
import { Loader2 } from "lucide-react";
import { ScrollArea } from "../ui/scroll-area.tsx";
import { remarkWikiLinks, resolveTarget, parseWikiLinks } from "../lib/remark-wiki-links.ts";
import { markdownComponents, REMARK_PLUGINS } from "../lib/markdown-components.tsx";
import { formatValue, parseFrontmatter } from "../lib/frontmatter.ts";
import { encodeFilePath } from "../lib/api.ts";
import { ViewBlockContext } from "./view-block.tsx";

interface PreviewProps {
  filePath: string | null;
  fileContent: string | null;
  isLoading: boolean;
  workspaceId: string | null;
  fileIndex: Map<string, string>;
  onFileClick: (path: string) => void;
}

function isMarkdownFile(path: string): boolean {
  return /\.(md|mdx|markdown)$/i.test(path);
}

function UnresolvedWiki({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{ color: "rgb(var(--cp-rgb-yellow) / 0.8)", background: "rgb(var(--cp-rgb-yellow) / 0.08)", padding: "0 3px", borderRadius: "3px", fontSize: "0.9em" }}
    >
      {children}
    </span>
  );
}

interface WikiLinkValueProps {
  text: string;
  workspaceId: string | null;
  fileIndex: Map<string, string>;
  onFileClick: (path: string) => void;
}

function WikiLinkValue({ text, workspaceId, fileIndex, onFileClick }: WikiLinkValueProps) {
  return (
    <>
      {parseWikiLinks(text).map((segment, i) => {
        if (segment.kind === "text") return segment.value;
        if (segment.kind === "image") return segment.raw;

        const resolved = workspaceId ? resolveTarget(segment.target, fileIndex) : null;
        if (!resolved) {
          return <UnresolvedWiki key={i}>{`[[${segment.target}]]`}</UnresolvedWiki>;
        }
        return (
          <a
            key={i}
            href="#"
            className="text-primary underline decoration-primary/40 hover:decoration-primary"
            onClick={(e) => { e.preventDefault(); onFileClick(resolved); }}
          >
            {segment.label}
          </a>
        );
      })}
    </>
  );
}

interface FrontmatterPanelProps {
  metadata: Record<string, unknown>;
  workspaceId: string | null;
  fileIndex: Map<string, string>;
  onFileClick: (path: string) => void;
}

export function FrontmatterPanel({ metadata, workspaceId, fileIndex, onFileClick }: FrontmatterPanelProps) {
  const entries = Object.entries(metadata);
  if (entries.length === 0) return null;

  return (
    <div className="mb-5 cp-cut-6 border border-cp-border bg-cp-surface3">
      <div className="px-3 py-1.5 border-b border-border flex items-center gap-1.5">
        <span className="inline-block w-1.5 h-1.5 bg-cp-yellow" />
        <span className="cp-label cp-label-sm text-foreground/70">
          Metadata
        </span>
      </div>
      <div className="px-3 py-2 space-y-1">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-baseline gap-2 text-sm">
            <span
              className="shrink-0 font-mono text-primary text-xs"
            >
              {key}
            </span>
            <span className="text-foreground/70">:</span>
            <span className="text-foreground font-mono break-all text-xs">
              <WikiLinkValue
                text={formatValue(value)}
                workspaceId={workspaceId}
                fileIndex={fileIndex}
                onFileClick={onFileClick}
              />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Preview({ filePath, fileContent, isLoading, workspaceId, fileIndex, onFileClick }: PreviewProps) {
  if (!filePath) return null;

  const isMd = isMarkdownFile(filePath);

  const remarkPlugins: PluggableList = [...REMARK_PLUGINS, remarkMath, remarkWikiLinks];

  const components: Components = {
    ...markdownComponents,
    img: ({ src, alt, node: _node }: ComponentProps<'img'> & ExtraProps) => {
      if (!src) return null;
      if (!src.startsWith("http") && !src.startsWith("data:")) {
        const dir = filePath?.includes("/") ? filePath.substring(0, filePath.lastIndexOf("/") + 1) : "";
        src = `/api/workspaces/${workspaceId}/files/${encodeFilePath(dir + src)}`;
      }
      return <img src={src} alt={alt} className="max-w-full h-auto rounded" />;
    },
    a: ({ href, children, node: _node }: ComponentProps<'a'> & ExtraProps) => {
      if (href?.startsWith("wiki-image://")) {
        const target = decodeURIComponent(href.replace("wiki-image://", ""));
        const resolved = workspaceId ? resolveTarget(target, fileIndex) : null;
        if (resolved) {
          return <img src={`/api/workspaces/${workspaceId}/files/${encodeFilePath(resolved)}`} alt={target} className="max-w-full h-auto rounded" />;
        }
        return <UnresolvedWiki>{`![[${target}]]`}</UnresolvedWiki>;
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
        return <UnresolvedWiki>{`[[${target}]]`}</UnresolvedWiki>;
      }
      return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
    },
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-primary/50" />
            </div>
          ) : fileContent === null ? (
            <div className="py-12 text-center cp-label text-destructive italic">
              Failed to load file
            </div>
          ) : isMd ? (
            <ViewBlockContext.Provider value={workspaceId ? { workspaceId, onFileClick } : null}>
              <div className="text-foreground/90 font-sans" style={{ lineHeight: '1.6' }}>
                {(() => {
                  const parsed = parseFrontmatter(fileContent);
                  const mdContent = parsed ? parsed.content : fileContent;
                  return (
                    <>
                      {parsed && (
                    <FrontmatterPanel
                      metadata={parsed.metadata}
                      workspaceId={workspaceId}
                      fileIndex={fileIndex}
                      onFileClick={onFileClick}
                    />
                  )}
                      <ReactMarkdown
                        remarkPlugins={remarkPlugins}
                        rehypePlugins={[rehypeMathjax]}
                        components={components}
                        urlTransform={(url) =>
                          url.startsWith("wiki://") || url.startsWith("wiki-image://")
                            ? url
                            : defaultUrlTransform(url)
                        }
                      >
                        {mdContent}
                      </ReactMarkdown>
                    </>
                  );
                })()}
              </div>
            </ViewBlockContext.Provider>
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
