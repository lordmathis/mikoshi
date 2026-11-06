import { Wrench, ShieldCheck, Check, X } from "lucide-react";
import { cn } from "../lib/utils.ts";
import { useState, useMemo, memo } from "react";
import ReactMarkdown from "react-markdown";
import { isWorkspaceChange, type Message, type PendingApproval } from "../lib/api.ts";
import { cyanMarkdownComponents, REMARK_PLUGINS } from "../lib/markdown-components.tsx";
import { CornerTriangle, MessageAvatar, Scanlines } from "./message-atoms.tsx";

interface ToolMessageProps {
  message: Message;
  pendingApproval?: PendingApproval | null;
  onApprove?: (messageId: string, scope: "once" | "always") => void | Promise<void>;
  onDeny?: (messageId: string) => void | Promise<void>;
}

function extractDisplayContent(content: string): string {
  try {
    const parsed: unknown = JSON.parse(content);
    if (isWorkspaceChange(parsed)) {
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
      <CornerTriangle position="bl" color="var(--color-cp-cyan)" size={14} opacity={0.3} />

      <Scanlines />

      <MessageAvatar
        background="rgb(var(--cp-rgb-cyan) / 0.1)"
        icon={<Wrench className="h-4 w-4 text-cp-cyan/70" />}
      />
      <div className="flex-1 space-y-2 overflow-hidden relative z-10">
        <div className="flex items-center gap-2">
          <p
            className="font-bold leading-none cp-label-lg text-cp-cyan"
          >
            // DATA_SHARD
          </p>
        </div>

        {pendingApproval ? (
          <ApprovalControls
            toolName={pendingApproval.tool_name}
            args={pendingApproval.arguments}
            resolving={resolving}
            onApprove={handleApprove}
            onDeny={handleDeny}
          />
        ) : (
          <>
            <button
              onClick={() => setShowToolResult(!showToolResult)}
              className="flex items-center gap-2 cp-label text-foreground/70 hover:text-foreground transition-colors max-lg:min-h-[36px]"
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
                <div className="text-foreground/90 tracking-[0.02em]" style={{ lineHeight: '1.6' }}>
                  <ReactMarkdown
                    remarkPlugins={REMARK_PLUGINS}
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
  args?: Record<string, unknown>;
  resolving: "once" | "always" | "deny" | null;
  onApprove: (scope: "once" | "always") => void | Promise<void>;
  onDeny: () => void | Promise<void>;
}

function formatToolArguments(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([key, value]) =>
      typeof value === "string" ? `${key}: ${value}` : `${key}: ${JSON.stringify(value)}`
    )
    .join("\n");
}

function ApprovalControls({ toolName, args, resolving, onApprove, onDeny }: ApprovalControlsProps) {
  const hasArgs = args && Object.keys(args).length > 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 cp-label" style={{ color: 'var(--color-cp-yellow)' }}>
        <ShieldCheck className="h-4 w-4" />
        <span>Approval required: {toolName}</span>
      </div>
      {hasArgs && (
        <div
          className="border p-3 cp-cut-10 max-h-48 overflow-y-auto"
          style={{
            borderColor: 'rgb(var(--cp-rgb-yellow) / 0.3)',
            background: 'rgb(var(--cp-rgb-yellow) / 0.05)',
          }}
        >
          <pre
            className="font-mono text-xs whitespace-pre-wrap break-words"
            style={{ color: 'var(--color-cp-text-warm)' }}
          >
            {formatToolArguments(args)}
          </pre>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => void onApprove("once")}
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
          onClick={() => void onApprove("always")}
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
          onClick={() => void onDeny()}
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
