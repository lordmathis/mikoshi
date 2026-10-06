import { Bot, AlertTriangle } from "lucide-react";
import { ChatMessage } from "./chat-message.tsx";
import { ToolMessage } from "./tool-message.tsx";
import { ScrollArea } from "../ui/scroll-area.tsx";
import { CornerTriangle, MessageAvatar } from "./message-atoms.tsx";
import { useEffect, memo, useRef } from "react";
import type { Message, PendingApproval } from "../lib/api.ts";
import { localCache } from "../lib/local-cache.ts";

const SCROLL_PERSIST_DELAY_MS = 300;

export function shouldFollowBottom(
  currentScrollTop: number,
  scrollHeight: number,
  clientHeight: number
): boolean {
  return scrollHeight - currentScrollTop - clientHeight <= 40;
}

interface ScrollPosition {
  top: number;
  atBottom: boolean;
}

function scrollKey(chatId: string): string {
  return `mikoshi-scroll:${chatId}`;
}

interface MessagesListProps {
  messages: Message[];
  isLoading: boolean;
  isSending: boolean;
  loadError?: string | null;
  currentConversationId: string | undefined;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  pendingApprovals?: Record<string, PendingApproval>;
  onApprove?: (messageId: string, scope: "once" | "always") => void;
  onDeny?: (messageId: string) => void;
  onBranch?: (messageId: string) => void;
  onRetry?: () => void;
  onEdit?: () => void;
}

export const MessagesList = memo(function MessagesList({
  messages,
  isLoading,
  isSending,
  loadError,
  currentConversationId,
  messagesEndRef,
  pendingApprovals,
  onApprove,
  onDeny,
  onBranch,
  onRetry,
  onEdit,
}: MessagesListProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLElement | null>(null);
  const atBottomRef = useRef(true);
  const restoredForChatRef = useRef<string | undefined>(undefined);
  const chatIdRef = useRef(currentConversationId);
  chatIdRef.current = currentConversationId;

  useEffect(() => {
    const viewport = scrollAreaRef.current?.querySelector<HTMLElement>(
      "[data-slot=scroll-area-viewport]"
    );
    viewportRef.current = viewport ?? null;
    if (!viewport) return;

    let persistTimer: ReturnType<typeof setTimeout> | undefined;
    const onScroll = () => {
      atBottomRef.current = shouldFollowBottom(
        viewport.scrollTop,
        viewport.scrollHeight,
        viewport.clientHeight
      );
      const chatId = chatIdRef.current;
      if (!chatId) return;
      const top = viewport.scrollTop;
      const atBottom = atBottomRef.current;
      clearTimeout(persistTimer);
      persistTimer = setTimeout(() => {
        localCache.set(scrollKey(chatId), { top, atBottom } satisfies ScrollPosition);
      }, SCROLL_PERSIST_DELAY_MS);
    };
    viewport.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      viewport.removeEventListener("scroll", onScroll);
      clearTimeout(persistTimer);
    };
  }, []);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport || !currentConversationId || messages.length === 0) return;
    if (restoredForChatRef.current === currentConversationId) return;
    restoredForChatRef.current = currentConversationId;

    const saved = localCache.get<ScrollPosition>(scrollKey(currentConversationId));
    if (saved && !saved.atBottom) {
      viewport.scrollTop = saved.top;
      atBottomRef.current = false;
    } else {
      viewport.scrollTop = viewport.scrollHeight;
      atBottomRef.current = true;
    }
  }, [currentConversationId, messages]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    if (isSending) {
      // Smooth-animated per-token scrolls jank; jump instead.
      if (atBottomRef.current) viewport.scrollTop = viewport.scrollHeight;
      return;
    }
    if (shouldFollowBottom(viewport.scrollTop, viewport.scrollHeight, viewport.clientHeight)) {
      viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isSending]);

  const lastUserMessageIndex = messages.reduce(
    (acc, m, i) => (m.role === "user" ? i : acc),
    -1
  );

  return (
    <ScrollArea ref={scrollAreaRef} className="flex-1 min-h-0">
      <div className="mx-auto max-w-3xl px-4 pb-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="cp-label text-muted-foreground uppercase tracking-widest">
              Loading data...
            </div>
          </div>
        ) : loadError ? (
          <div className="flex items-center justify-center gap-2 py-12">
            <AlertTriangle className="h-4 w-4 text-[var(--color-cp-red)]" />
            <div className="cp-label text-[var(--color-cp-red)]">
              {loadError}
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="text-2xl font-bold text-primary mb-2" style={{ letterSpacing: '0.1em' }}>
                &gt;_
              </div>
              <p className="cp-label text-foreground mb-2" style={{ color: 'var(--color-cp-yellow)' }}>
                SYSTEM READY
              </p>
              <p className="cp-label text-muted-foreground">
                {currentConversationId
                  ? "Type a command below to begin transmission"
                  : "Select a session from the sidebar or initialize a new one"}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((message, index) => {
              const isLastMessage = index === messages.length - 1;
              const isLastAssistantMessage = isLastMessage && message.role === "assistant";
              const isLastUserMessage = lastUserMessageIndex !== -1 && index === lastUserMessageIndex;
              
              if (message.role === "tool") {
                return (
                  <ToolMessage
                    key={message.id}
                    message={message}
                    pendingApproval={pendingApprovals?.[message.id]}
                    onApprove={onApprove}
                    onDeny={onDeny}
                  />
                );
              }

              if (message.role === "error") {
                return <ErrorMessage key={message.id} message={message} />;
              }
              
              return (
                <ChatMessage 
                  key={message.id} 
                  message={message} 
                  onBranch={onBranch} 
                  onRetry={isLastAssistantMessage ? onRetry : undefined}
                  onEdit={onEdit}
                  isLastUserMessage={isLastUserMessage}
                />
              );
            })}
            {isSending && (
                <div
                  className="group relative flex gap-4 px-4 py-6 sm:px-6 bg-cp-surface4 overflow-hidden cp-cut-z-16"
                  style={{
                    border: "1px solid rgb(var(--cp-rgb-red) / 0.2)",
                  }}
                >
                  <CornerTriangle position="tr" color="var(--color-cp-red)" />
                  <MessageAvatar
                    background="rgb(var(--cp-rgb-red) / 0.15)"
                    icon={<Bot className="h-5 w-5 text-[var(--color-cp-red)]" />}
                  />
                  <div className="flex-1 space-y-2 overflow-hidden">
                    <div className="flex items-center gap-2">
                        <p className="cp-label font-bold" style={{ color: 'var(--color-cp-red)' }}>
                         // DAEMON
                       </p>
                     </div>
                     <div className="flex items-center gap-2 cp-label text-muted-foreground">
                       <div className="flex gap-1">
                         <span className="animate-bounce text-foreground" style={{ animationDelay: "0ms" }}>
                           &#9654;
                         </span>
                         <span className="animate-bounce text-foreground" style={{ animationDelay: "150ms" }}>
                           &#9654;
                         </span>
                         <span className="animate-bounce text-foreground" style={{ animationDelay: "300ms" }}>
                           &#9654;
                         </span>
                       </div>
                       <span className="text-foreground">Breaching...</span>
                     </div>
                   </div>
                 </div>
               )}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  );
});

function ErrorMessage({ message }: { message: Message }) {
  return (
    <div
      className="group relative flex gap-4 px-4 py-6 sm:px-6 bg-cp-surface4 overflow-hidden cp-cut-z-16"
      style={{ border: "1px solid rgb(var(--cp-rgb-red) / 0.4)" }}
    >
      <CornerTriangle position="tr" color="var(--color-cp-red)" />
      <MessageAvatar
        background="rgb(var(--cp-rgb-red) / 0.15)"
        icon={<AlertTriangle className="h-4 w-4 text-[var(--color-cp-red)]" />}
      />
      <div className="flex-1 space-y-2 overflow-hidden relative z-10">
        <p
          className="font-bold leading-none"
          style={{
            color: 'var(--color-cp-red)',
            fontSize: '14px',
            letterSpacing: '0.16em',
            textTransform: 'uppercase',
          }}
        >
          // ERROR
        </p>
        <div
          className="text-foreground/90 font-sans break-words"
          style={{ lineHeight: '1.6', overflowWrap: 'anywhere' }}
        >
          {message.content}
        </div>
      </div>
    </div>
  );
}
