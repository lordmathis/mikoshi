import { Plus, Trash2, X } from "lucide-react";
import { Button } from "./ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";
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
        <TooltipProvider delayDuration={300}>
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
                <div
                  key={conversation.id}
                  className={`group relative flex items-center transition-all duration-200 cursor-pointer border ${
                    isActive
                      ? "bg-primary/5 border-primary/30 shadow-[0_0_15px_rgba(245,216,0,0.05)]"
                      : "bg-white/[0.02] border-white/5 hover:border-white/10 hover:bg-white/[0.04]"
                  }`}
                  style={{
                    clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%)",
                  }}
                  onClick={() => onConversationSelect(conversation.id)}
                >
                  <div
                    className={`absolute left-0 top-0 bottom-0 w-[2px] transition-all duration-300 ${
                      isActive ? "bg-primary" : "bg-transparent group-hover:bg-white/20"
                    }`}
                  />

                  <div className="flex-1 min-w-0 px-4 py-3">
                    <div className="flex items-center justify-between mb-1">
                      <div
                        className={`text-[9px] font-bold tracking-widest ${
                          isActive ? "text-cyan" : "text-muted-foreground"
                        }`}
                      >
                        [{conversation.id.slice(0, 4).toUpperCase()}]
                      </div>
                      <div className="flex items-center gap-2">
                        {hasWorkspace && (
                          <span className="text-[8px] text-primary/50 uppercase">NODE</span>
                        )}
                        <span className="text-[8px] text-muted-foreground opacity-50 uppercase">
                          {conversation.timestamp}
                        </span>
                      </div>
                    </div>

                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div
                          className={`truncate text-[13px] font-medium tracking-tight ${
                            isActive ? "text-foreground" : "text-foreground/60"
                          }`}
                        >
                          {conversation.title || "NULL_SIGNAL"}
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-xs">
                        <p>{conversation.title || "NULL_SIGNAL"}</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>

                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 mr-2 opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm(`Terminate session ${conversation.id.slice(0, 4)}?`)) {
                        onDeleteConversation(conversation.id);
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              );
            })
          )}
        </TooltipProvider>
      </div>
    </>
  );
}
