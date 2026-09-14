import { Bot, AlertTriangle } from "lucide-react";
import { ChatMessage } from "./chat-message";
import { ToolMessage } from "./tool-message";
import { ScrollArea } from "./ui/scroll-area";
import { CornerTriangle, MessageAvatar } from "./message-atoms";
import { useEffect, memo } from "react";
import type { Message, PendingApproval } from "../lib/api";

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
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending, messagesEndRef]);

  const lastUserMessageIndex = messages.reduce(
    (acc, m, i) => (m.role === "user" ? i : acc),
    -1
  );

  return (
    <ScrollArea className="flex-1 min-h-0">
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
