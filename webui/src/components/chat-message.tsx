import { Bot, User, Brain, File, GitBranch, RotateCw, Edit2, Copy, Check, Link, Volume2 } from "lucide-react";
import { cn } from "../lib/utils";
import ReactMarkdown from "react-markdown";
import "highlight.js/styles/github-dark.css";
import { useState, useRef, useEffect } from "react";
import { Button } from "./ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";
import { type Message } from "../lib/api";
import { markdownComponents, REMARK_PLUGINS, REHYPE_PLUGINS } from "../lib/markdown-components";

interface ChatMessageProps {
  message: Message;
  onBranch?: (messageId: string) => void;
  onRetry?: () => void;
  onEdit?: () => void;
  isLastUserMessage?: boolean;
}

export function ChatMessage({ message, onBranch, onRetry, onEdit, isLastUserMessage }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [showReasoning, setShowReasoning] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleTTS = async () => {
    if (isSpeaking) return;
    try {
      setIsSpeaking(true);
      const { api } = await import("../lib/api");
      const audioBlob = await api.generateSpeech(message.content);
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        audioRef.current = null;
        setIsSpeaking(false);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(audioUrl);
        audioRef.current = null;
        setIsSpeaking(false);
      };
      await audio.play();
    } catch (err) {
      console.error("Failed to speak:", err);
      audioRef.current = null;
      setIsSpeaking(false);
    }
  };

  const groupedFiles = (() => {
    if (!message.files) return [];
    
    const groups: { source: string | null; files: typeof message.files }[] = [];
    const filesBySource = new Map<string | null, typeof message.files>();
    
    for (const file of message.files) {
      const key = file.source ?? null;
      if (!filesBySource.has(key)) {
        filesBySource.set(key, []);
      }
      filesBySource.get(key)!.push(file);
    }
    
    for (const [source, files] of filesBySource) {
      groups.push({ source, files });
    }
    
    return groups;
  })();

  const renderFileChip = (file: { id: string; filename: string }) => (
    <div
      key={file.id}
      className="flex items-center gap-1.5 border border-border bg-[rgba(245,216,0,0.06)] px-2 py-1 text-xs"
      style={{ clipPath: "polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)" }}
    >
      <File className="h-3.5 w-3.5 text-primary/60" />
      <span className="font-medium text-foreground/80">{file.filename}</span>
    </div>
  );

  const renderSourceChip = (source: string, fileCount: number) => {
    const repo = source.includes(':') ? source.split(':').slice(1).join(':') : source;
    return (
      <div
        className="flex items-center gap-1.5 border border-[rgba(0,212,255,0.2)] bg-[rgba(0,212,255,0.06)] px-2 py-1 text-xs"
        style={{ clipPath: "polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)" }}
      >
        <Link className="h-3.5 w-3.5 text-[var(--color-cp-cyan)]" />
        <span className="font-medium text-[var(--color-cp-cyan)]">
          {fileCount} file{fileCount !== 1 ? 's' : ''} from {repo}
        </span>
      </div>
    );
  };

  const userClipPath = "polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 16px 100%, 0 calc(100% - 16px))";
  const assistantClipPath = "polygon(0 16px, 16px 0, 100% 0, 100% calc(100% - 16px), calc(100% - 16px) 100%, 0 100%)";

  return (
    <div
      className={cn(
        "group relative flex gap-4 px-4 py-6 sm:px-6 border overflow-hidden",
        isUser ? "bg-[#0f0f0d]" : "bg-[#12110e]"
      )}
      style={{
        borderColor: isUser ? "rgba(245, 216, 0, 0.2)" : "rgba(230, 51, 41, 0.2)",
        clipPath: isUser ? userClipPath : assistantClipPath,
        boxShadow: "none",
        transition: "border-color 0.15s, box-shadow 0.15s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = isUser ? "rgba(245, 216, 0, 0.4)" : "rgba(230, 51, 41, 0.35)";
        e.currentTarget.style.boxShadow = isUser
          ? "0 0 12px rgba(245, 216, 0, 0.08)"
          : "0 0 12px rgba(230, 51, 41, 0.08)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = isUser ? "rgba(245, 216, 0, 0.2)" : "rgba(230, 51, 41, 0.2)";
        e.currentTarget.style.boxShadow = "none";
      }}
    >
      {isUser ? (
        <div
          className="absolute top-0 right-0 w-[16px] h-[16px] opacity-40"
          style={{ background: '#f5d800', clipPath: 'polygon(0 0, 100% 100%, 100% 0)' }}
        />
      ) : (
        <div
          className="absolute top-0 left-0 w-[16px] h-[16px] opacity-40"
          style={{ background: '#e63329', clipPath: 'polygon(0 0, 100% 0, 0 100%)' }}
        />
      )}

      {/* Scanlines */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(245,216,0,0.012) 3px, rgba(245,216,0,0.012) 4px)",
        }}
      />

      <div className="flex-shrink-0 relative z-10">
        <div
          className="flex h-8 w-8 items-center justify-center"
          style={{
            background: isUser ? "rgba(245, 216, 0, 0.15)" : "rgba(230, 51, 41, 0.15)",
            clipPath: "polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)",
          }}
        >
          {isUser ? (
            <User className="h-4 w-4 text-primary" />
          ) : (
            <Bot className="h-4 w-4 text-[var(--color-cp-red)]" />
          )}
        </div>
      </div>
      <div className="flex-1 space-y-2 overflow-hidden relative z-10">
        <div className="flex items-center gap-2">
          <p
            className="font-bold leading-none"
            style={{
              color: isUser ? '#f5d800' : '#e63329',
              fontFamily: 'var(--font-mono)',
              fontSize: '14px',
              letterSpacing: '0.16em',
              textTransform: 'uppercase',
            }}
          >
            {isUser ? "// UPLINK" : "// DAEMON"}
          </p>
        </div>
        
        {isUser && message.files && message.files.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {groupedFiles.map(({ source, files }) => {
              if (source === null) {
                return files.map(file => renderFileChip(file));
              } else {
                return <div key={source}>{renderSourceChip(source, files.length)}</div>;
              }
            })}
          </div>
        )}
        
        {!isUser && message.reasoning_content && (
          <div className="mb-2">
            <button
              onClick={() => setShowReasoning(!showReasoning)}
              className="flex items-center gap-2 cp-label hover:text-foreground transition-colors"
              style={{ color: '#a89e88' }}
            >
              <Brain className="h-3.5 w-3.5" />
              <span>{showReasoning ? "Hide" : "Show"} reasoning</span>
              <svg
                className={cn(
                  "h-3 w-3 transition-transform",
                  showReasoning && "rotate-180"
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
            
            {showReasoning && (
              <div className="mt-2 border border-border bg-[rgba(0,212,255,0.03)] p-3"
                   style={{ clipPath: "polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 0 100%)" }}>
                <div className="text-muted-foreground">
                  <ReactMarkdown
                    remarkPlugins={REMARK_PLUGINS}
                    rehypePlugins={REHYPE_PLUGINS}
                    components={markdownComponents}
                  >
                    {message.reasoning_content}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )}
        
        {!isUser && message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mb-2">
            <div className="flex items-start gap-2 cp-label text-muted-foreground">
              <span className="font-medium text-muted-foreground">TOOLS_USED:</span>
              <div className="flex flex-wrap gap-1.5">
                {message.tool_calls.map((tool, index) => (
                  <TooltipProvider key={index} delayDuration={300}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span
                          className="inline-flex items-center gap-1 border border-[rgba(138,130,112,0.2)] bg-[rgba(138,130,112,0.05)] px-2 py-0.5 text-xs hover:border-[rgba(138,130,112,0.35)] transition-colors cursor-default"
                          style={{
                            fontFamily: 'var(--font-mono)',
                            clipPath: "polygon(0 0, calc(100% - 6px) 0, 100% 6px, 100% 100%, 0 100%)",
                            color: '#e8e0c8',
                          }}
                        >
                          {tool.name.replace(/^\w+__/, '')}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-md">
                        <div className="space-y-1">
                          <p className="font-semibold text-primary">{tool.name}</p>
                          {Object.keys(tool.arguments).length > 0 && (
                            <div className="text-xs">
                              <p className="font-medium mb-1">Arguments:</p>
                              <pre className="overflow-auto max-h-40 bg-background/50 p-1">
                                {JSON.stringify(tool.arguments, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                ))}
              </div>
            </div>
          </div>
        )}
        
        <div className="text-foreground/90" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', lineHeight: '1.6' }}>
          <ReactMarkdown
            remarkPlugins={REMARK_PLUGINS}
            rehypePlugins={REHYPE_PLUGINS}
            components={markdownComponents}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
      
      {(onBranch || (onRetry && !isUser) || (onEdit && isUser && isLastUserMessage) || !isUser) && (
        <div className="absolute right-4 top-6 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          {!isUser && (
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={handleCopy}
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                    <span className="sr-only">Copy</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left">
                  <p>{copied ? "Copied!" : "Copy"}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          
          {!isUser && (
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={handleTTS}
                    disabled={isSpeaking}
                  >
                    <Volume2 className={cn("h-4 w-4", isSpeaking && "animate-pulse")} />
                    <span className="sr-only">Speak</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left">
                  <p>{isSpeaking ? "Speaking..." : "Speak"}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          
          {onEdit && isUser && isLastUserMessage && (
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={onEdit}
                  >
                    <Edit2 className="h-4 w-4" />
                    <span className="sr-only">Edit</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left">
                  <p>Edit</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          
          {onRetry && !isUser && (
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={onRetry}
                  >
                    <RotateCw className="h-4 w-4" />
                    <span className="sr-only">Retry</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left">
                  <p>Retry</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          
          {onBranch && (
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={() => onBranch(message.id)}
                  >
                    <GitBranch className="h-4 w-4" />
                    <span className="sr-only">Branch</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left">
                  <p>Branch</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      )}
    </div>
  );
}
