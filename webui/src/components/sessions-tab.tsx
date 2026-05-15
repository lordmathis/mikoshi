import { Plus, X } from "lucide-react";
import { Button } from "./ui/button";
import { SidebarItem } from "./sidebar-item";
import type { Conversation } from "./sidebar";

interface SessionsTabProps {
  conversations: Conversation[];
  currentConversationId?: string;
  activeWorkspaceId: string | null;
  workspaces: { id: string; name: string }[];
  onConversationSelect: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onClearFilter: () => void;
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
  isLoading = false,
}: SessionsTabProps) {
  let filtered: Conversation[];
  if (activeWorkspaceId) {
    filtered = conversations.filter(
      (c) => c.workspace_id === activeWorkspaceId,
    );
  } else {
    filtered = conversations.filter((c) => !c.workspace_id);
  }

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
        {isLoading ? (
          <div className="py-12 text-center cp-label opacity-40 animate-pulse">Syncing...</div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center cp-label opacity-20 italic">
            {activeWorkspaceId ? "No sessions bound to this node" : "No sessions found"}
          </div>
        ) : (
          filtered.map((conversation) => {
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
      </div>
    </>
  );
}
