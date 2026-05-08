import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeMathjax from "rehype-mathjax";
import "highlight.js/styles/github-dark.css";
import { Loader2, X, File } from "lucide-react";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";

const markdownComponents = {
  h1: ({ children, ...props }: any) => (
    <h1 className="text-2xl font-bold mt-6 mb-4 first:mt-0 text-foreground" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }: any) => (
    <h2 className="text-xl font-bold mt-5 mb-3 first:mt-0 text-foreground" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }: any) => (
    <h3 className="text-lg font-bold mt-4 mb-2 first:mt-0 text-foreground" {...props}>{children}</h3>
  ),
  p: ({ children, ...props }: any) => (
    <p className="mb-4 last:mb-0 text-foreground/90" {...props}>{children}</p>
  ),
  ul: ({ children, ...props }: any) => (
    <ul className="list-disc pl-6 mb-4 space-y-1" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }: any) => (
    <ol className="list-decimal pl-6 mb-4 space-y-1" {...props}>{children}</ol>
  ),
  code: ({ inline, className, children, ...props }: any) => {
    return inline ? (
      <code className="bg-[rgba(245,216,0,0.08)] px-1.5 py-0.5 text-xs text-primary/90" {...props}>
        {children}
      </code>
    ) : (
      <code className={className} {...props}>{children}</code>
    );
  },
  table: ({ children, ...props }: any) => (
    <div className="overflow-x-auto mb-4">
      <table className="w-full border-collapse border border-[rgba(245,216,0,0.2)]" {...props}>{children}</table>
    </div>
  ),
  thead: ({ children, ...props }: any) => (
    <thead className="bg-[rgba(245,216,0,0.06)]" {...props}>{children}</thead>
  ),
  th: ({ children, ...props }: any) => (
    <th className="border border-[rgba(245,216,0,0.2)] px-3 py-2 text-left text-sm font-bold text-foreground" {...props}>{children}</th>
  ),
  td: ({ children, ...props }: any) => (
    <td className="border border-[rgba(245,216,0,0.15)] px-3 py-2 text-sm text-foreground/80" {...props}>{children}</td>
  ),
  tr: ({ children, ...props }: any) => (
    <tr className="even:bg-[rgba(245,216,0,0.03)]" {...props}>{children}</tr>
  ),
};

interface FilePreviewProps {
  filePath: string | null;
  fileContent: string | null;
  isLoading: boolean;
  onClose: () => void;
}

function isMarkdownFile(path: string): boolean {
  return /\.(md|mdx|markdown)$/i.test(path);
}

export function FilePreview({ filePath, fileContent, isLoading, onClose }: FilePreviewProps) {
  if (!filePath) return null;

  const fileName = filePath.split("/").pop() || filePath;
  const isMd = isMarkdownFile(filePath);

  return (
    <div className="flex flex-col h-full overflow-hidden border-r" style={{ borderColor: "rgba(245, 216, 0, 0.1)" }}>
      <div
        className="flex items-center justify-between px-4 py-2 shrink-0 border-b"
        style={{
          borderColor: "rgba(245, 216, 0, 0.1)",
          background: "rgba(16,16,14,0.95)",
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
                remarkPlugins={[remarkGfm, remarkBreaks, remarkMath]}
                rehypePlugins={[rehypeHighlight, rehypeMathjax]}
                components={markdownComponents}
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
