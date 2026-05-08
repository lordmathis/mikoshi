import { Bot } from "lucide-react";
import { ChatMessage } from "./chat-message";
import { ToolMessage } from "./tool-message";
import { ScrollArea } from "./ui/scroll-area";
import { useEffect } from "react";
import type { Message } from "../lib/api";

interface MessagesListProps {
  messages: Message[];
  isLoading: boolean;
  isSending: boolean;
  currentConversationId: string | undefined;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  onBranch?: (messageId: string) => void;
  onRetry?: () => void;
  onEdit?: () => void;
}

export function MessagesList({
  messages,
  isLoading,
  isSending,
  currentConversationId,
  messagesEndRef,
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
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="text-2xl font-bold text-primary mb-2" style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                &gt;_
              </div>
              <p className="cp-label text-foreground mb-2" style={{ color: '#f5d800' }}>
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
                return <ToolMessage key={message.id} message={message} />;
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
                  className="group relative flex gap-4 px-4 py-6 sm:px-6 bg-[#12110e] overflow-hidden"
                  style={{
                    clipPath: "polygon(0 16px, 16px 0, 100% 0, 100% calc(100% - 16px), calc(100% - 16px) 100%, 0 100%)",
                    border: "1px solid rgba(230, 51, 41, 0.2)",
                  }}
                >
                  <div
                    className="absolute top-0 left-0 w-[16px] h-[16px] opacity-40"
                    style={{ background: '#e63329', clipPath: 'polygon(0 0, 100% 0, 0 100%)' }}
                  />
                  <div className="flex-shrink-0">
                    <div
                      className="flex h-8 w-8 items-center justify-center"
                      style={{
                        background: "rgba(230, 51, 41, 0.15)",
                        clipPath: "polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)",
                      }}
                    >
                      <Bot className="h-5 w-5 text-[var(--color-cp-red)]" />
                    </div>
                  </div>
                  <div className="flex-1 space-y-2 overflow-hidden">
                    <div className="flex items-center gap-2">
                      <p className="cp-label font-bold" style={{ color: '#e63329' }}>
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
}
