import { Wrench, ShieldCheck, Check, X } from "lucide-react";
import { cn } from "../lib/utils";
import { useState, useMemo, memo } from "react";
import ReactMarkdown from "react-markdown";
import "highlight.js/styles/github-dark.css";
import type { Message, PendingApproval } from "../lib/api";
import { cyanMarkdownComponents, REMARK_PLUGINS, REHYPE_PLUGINS } from "../lib/markdown-components";

interface ToolMessageProps {
  message: Message;
  pendingApproval?: PendingApproval | null;
  onApprove?: (messageId: string, scope: "once" | "always") => void;
  onDeny?: (messageId: string) => void;
}

function extractDisplayContent(content: string): string {
  try {
    const parsed = JSON.parse(content);
    if (parsed && parsed.__workspace === true && typeof parsed.summary === "string") {
      return parsed.summary;
    }
  } catch {}
  return content;
}

export const ToolMessage = memo(function ToolMessage({
  message,
  pendingApproval,
  onApprove,
  onDeny,
}: ToolMessageProps) {
  const [showToolResult, setShowToolResult] = useState(false);
  const [resolving, setResolving] = useState<"once" | "always" | "deny" | null>(null);
  const displayContent = useMemo(() => extractDisplayContent(message.content), [message.content]);

  const handleApprove = async (scope: "once" | "always") => {
    setResolving(scope);
    try {
      await onApprove?.(message.id, scope);
    } finally {
      setResolving(null);
    }
  };

  const handleDeny = async () => {
    setResolving("deny");
    try {
      await onDeny?.(message.id);
    } finally {
      setResolving(null);
    }
  };

  return (
    <div
      className="group relative flex gap-4 px-4 py-3 sm:px-6 border overflow-hidden bg-cp-surface4 cp-cut-x-14 cp-hover-tool"
    >
      <div
        className="absolute top-0 right-0 w-[14px] h-[14px] opacity-30 cp-tri-bl"
        style={{ background: 'var(--color-cp-cyan)' }}
      />

      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `repeating-linear-gradient(0deg, transparent, transparent 3px, rgb(var(--cp-rgb-yellow) / 0.012) 3px, rgb(var(--cp-rgb-yellow) / 0.012) 4px)`,
        }}
      />

      <div className="flex-shrink-0 relative z-10">
        <div
          className="flex h-8 w-8 items-center justify-center cp-cut-8"
          style={{
            background: "rgb(var(--cp-rgb-cyan) / 0.1)",
          }}
        >
          <Wrench className="h-4 w-4 text-cp-cyan/70" />
        </div>
      </div>
      <div className="flex-1 space-y-2 overflow-hidden relative z-10">
        <div className="flex items-center gap-2">
          <p
            className="font-bold leading-none"
            style={{
              color: 'var(--color-cp-cyan)',
              fontSize: '14px',
              letterSpacing: '0.16em',
              textTransform: 'uppercase',
            }}
          >
            // DATA_SHARD
          </p>
        </div>

        {pendingApproval ? (
          <ApprovalControls
            toolName={pendingApproval.tool_name}
            resolving={resolving}
            onApprove={handleApprove}
            onDeny={handleDeny}
          />
        ) : (
          <>
            <button
              onClick={() => setShowToolResult(!showToolResult)}
              className="flex items-center gap-2 cp-label transition-colors"
              style={{ color: 'var(--color-cp-text-muted)' }}
            >
              <Wrench className="h-3.5 w-3.5" />
              <span>{showToolResult ? "Hide" : "Show"} result</span>
              <svg
                className={cn(
                  "h-3 w-3 transition-transform",
                  showToolResult && "rotate-180"
                )}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            {showToolResult && (
              <div className="mt-2 border border-border bg-cp-cyan/3 p-3 cp-cut-10">
                <div className="text-foreground/90" style={{ letterSpacing: '0.02em', lineHeight: '1.6' }}>
                  <ReactMarkdown
                    remarkPlugins={REMARK_PLUGINS}
                    rehypePlugins={REHYPE_PLUGINS}
                    components={cyanMarkdownComponents}
                  >
                    {displayContent}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
});

interface ApprovalControlsProps {
  toolName: string;
  resolving: "once" | "always" | "deny" | null;
  onApprove: (scope: "once" | "always") => void;
  onDeny: () => void;
}

function ApprovalControls({ toolName, resolving, onApprove, onDeny }: ApprovalControlsProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 cp-label" style={{ color: 'var(--color-cp-yellow)' }}>
        <ShieldCheck className="h-4 w-4" />
        <span>Approval required: {toolName}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onApprove("once")}
          disabled={resolving !== null}
          className="flex items-center gap-1.5 cp-label px-3 py-1.5 cp-cut-8 transition-colors disabled:opacity-50"
          style={{
            color: 'var(--color-primary-foreground)',
            background: 'var(--color-cp-yellow)',
          }}
        >
          <Check className="h-3.5 w-3.5" />
          <span>{resolving === "once" ? "…" : "Allow"}</span>
        </button>
        <button
          onClick={() => onApprove("always")}
          disabled={resolving !== null}
          className="flex items-center gap-1.5 cp-label px-3 py-1.5 cp-cut-8 border transition-colors disabled:opacity-50"
          style={{
            color: 'var(--color-cp-cyan)',
            borderColor: 'rgb(var(--cp-rgb-cyan) / 0.4)',
            background: 'rgb(var(--cp-rgb-cyan) / 0.06)',
          }}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          <span>{resolving === "always" ? "…" : "Always allow"}</span>
        </button>
        <button
          onClick={onDeny}
          disabled={resolving !== null}
          className="flex items-center gap-1.5 cp-label px-3 py-1.5 cp-cut-8 border transition-colors disabled:opacity-50"
          style={{
            color: 'var(--color-cp-red)',
            borderColor: 'rgb(var(--cp-rgb-red) / 0.4)',
            background: 'rgb(var(--cp-rgb-red) / 0.06)',
          }}
        >
          <X className="h-3.5 w-3.5" />
          <span>{resolving === "deny" ? "…" : "Deny"}</span>
        </button>
      </div>
    </div>
  );
}
