import { useEffect, useRef } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "../ui/button.tsx";
import { EmptyState } from "../shared/empty-state.tsx";
import { SidebarItem } from "./sidebar-item.tsx";
import type { Conversation } from "./sidebar.tsx";

interface SessionsTabProps {
  conversations: Conversation[];
  currentConversationId?: string;
  activeWorkspaceId: string | null;
  workspaces: { id: string; name: string }[];
  onConversationSelect: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onClearFilter: () => void;
  hasMore: boolean;
  onLoadMore: () => void;
  isLoading?: boolean;
}

export function SessionsTab({
  conversations,
  currentConversationId,
  activeWorkspaceId,
  workspaces,
  onConversationSelect,
  onNewConversation,
  onDeleteConversation,
  onClearFilter,
  hasMore,
  onLoadMore,
  isLoading = false,
}: SessionsTabProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && hasMore && !isLoading) {
        onLoadMore();
      }
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isLoading, onLoadMore]);

  const activeWorkspaceName = activeWorkspaceId
    ? workspaces.find((w) => w.id === activeWorkspaceId)?.name
    : null;

  return (
    <>
      <div className="px-3 py-3">
        <Button
          variant="outline"
          className="w-full justify-between gap-2 text-[14px] h-10 border-primary/20 hover:border-primary/50 bg-primary/5 group text-cyan"
          onClick={onNewConversation}
        >
          <span className="flex items-center gap-2">
            <Plus className="h-3.5 w-3.5" />
            JACK_IN
          </span>
        </Button>
      </div>

      {activeWorkspaceId && activeWorkspaceName && (
        <div className="mx-3 mb-2 flex items-center gap-2 border border-primary/20 bg-primary/5 px-3 py-1.5">
          <span className="cp-label text-primary text-[10px]">Bound to: {activeWorkspaceName}</span>
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 ml-auto opacity-60 hover:opacity-100"
            onClick={onClearFilter}
          >
            <X className="h-3 w-3" />
          </Button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-3 pb-6 space-y-2">
        {conversations.length === 0 && !isLoading ? (
          <EmptyState>
            {activeWorkspaceId ? "No sessions bound to this node" : "No sessions found"}
          </EmptyState>
        ) : (
          conversations.map((conversation) => {
            const isActive = currentConversationId === conversation.id;
            const hasWorkspace = !!conversation.workspace_id;
            return (
              <SidebarItem
                key={conversation.id}
                id={conversation.id}
                isActive={isActive}
                label={conversation.title || "NULL_SIGNAL"}
                sublabel={`[${conversation.id.slice(0, 4).toUpperCase()}]`}
                badge={hasWorkspace ? "NODE" : undefined}
                confirmMessage={`Terminate session ${conversation.id.slice(0, 4)}?`}
                onClick={() => onConversationSelect(conversation.id)}
                onDelete={() => onDeleteConversation(conversation.id)}
              >
                <span className="text-[8px] text-muted-foreground opacity-50 uppercase">
                  {conversation.timestamp}
                </span>
              </SidebarItem>
            );
          })
        )}
        <div ref={sentinelRef} className="py-2 text-center cp-label opacity-40">
          {isLoading && <span className="animate-pulse inline-block">Syncing...</span>}
        </div>
      </div>
    </>
  );
}
