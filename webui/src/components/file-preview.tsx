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
}

function isMarkdownFile(path: string): boolean {
  return /\.(md|mdx|markdown)$/i.test(path);
}

export function FilePreview({ filePath, fileContent, isLoading, onClose, workspaceId, fileIndex, onFileClick }: FilePreviewProps) {
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
    <div className="flex flex-col h-full overflow-hidden border-r" style={{ borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)" }}>
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
            <div className="text-foreground/90" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', lineHeight: '1.6' }}>
              <ReactMarkdown
                remarkPlugins={remarkPlugins}
                rehypePlugins={[...REHYPE_PLUGINS, rehypeMathjax]}
                components={components}
                urlTransform={(url) => {
                  if (url.startsWith("wiki://") || url.startsWith("wiki-image://")) return url;
                  return url;
                }}
              >
                {fileContent}
              </ReactMarkdown>
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
