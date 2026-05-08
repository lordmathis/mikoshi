import { PanelLeftClose, Plus, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";

export interface Conversation {
  id: string;
  title: string;
  timestamp: string;
  preview?: string;
  workspace_id?: string | null;
}

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  conversations: Conversation[];
  currentConversationId?: string;
  onConversationSelect?: (conversationId: string) => void;
  onNewConversation?: () => void;
  onDeleteConversation?: (conversationId: string) => void;
  isLoading?: boolean;
}

export function Sidebar({
  isOpen,
  onToggle,
  conversations,
  currentConversationId,
  onConversationSelect,
  onNewConversation,
  onDeleteConversation,
  isLoading = false,
}: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-background/80 backdrop-blur-sm lg:hidden"
          onClick={onToggle}
        />
      )}

      <div
        className={`
          fixed left-0 top-0 z-40 h-screen w-[290px] transform border-r bg-[#0a0a0c]/95 backdrop-blur-md transition-transform duration-200 ease-in-out
          lg:relative lg:z-0
          ${isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0 lg:w-0 lg:border-0"}
        `}
        style={{ borderRightColor: 'rgba(245, 216, 0, 0.1)' }}
      >
        <div className={`flex h-full flex-col overflow-hidden ${isOpen ? "" : "lg:hidden"}`}>
          {/* Header */}
          <div className="flex shrink-0 items-center justify-between px-4 py-4 border-b border-white/5">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-primary rotate-45" />
              <h2 className="text-[10px] font-black text-primary uppercase tracking-[0.25em]">
                Sessions
              </h2>
            </div>
            <Button variant="ghost" size="icon" onClick={onToggle} className="h-7 w-7 opacity-50 hover:opacity-100">
              <PanelLeftClose className="h-4 w-4" />
            </Button>
          </div>

          {/* Action Bar */}
          <div className="px-3 py-4">
            <Button
variant="outline"
               className="w-full justify-between gap-2 text-[14px] h-10 border-primary/20 hover:border-primary/50 bg-primary/5 group text-cyan"
              onClick={onNewConversation}
            >
              <span className="flex items-center gap-2">
                <Plus className="h-3.5 w-3.5" />
                INITIALIZE_NEW_SESSION
              </span>
            </Button>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto px-3 pb-6 space-y-2">
            <TooltipProvider delayDuration={300}>
              {isLoading ? (
                <div className="py-12 text-center cp-label opacity-40 animate-pulse">Syncing...</div>
              ) : conversations.length === 0 ? (
                <div className="py-12 text-center cp-label opacity-20 italic">No sessions found</div>
              ) : (
                conversations.map((conversation) => {
                  const isActive = currentConversationId === conversation.id;
                  return (
                    <div
                      key={conversation.id}
                      className={`
                        group relative flex items-center transition-all duration-200 cursor-pointer border
                        ${isActive 
                          ? "bg-primary/5 border-primary/30 shadow-[0_0_15px_rgba(245,216,0,0.05)]" 
                          : "bg-white/[0.02] border-white/5 hover:border-white/10 hover:bg-white/[0.04]"
                        }
                      `}
                      style={{
                        clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%)",
                      }}
                      onClick={() => onConversationSelect?.(conversation.id)}
                    >
                      {/* Left Accent Bar */}
                      <div className={`absolute left-0 top-0 bottom-0 w-[2px] transition-all duration-300 ${
                        isActive ? "bg-primary" : "bg-transparent group-hover:bg-white/20"
                      }`} />

                      <div className="flex-1 min-w-0 px-4 py-3">
                        <div className="flex items-center justify-between mb-1">
                          <div className={`text-[9px] font-bold tracking-widest ${isActive ? "text-cyan" : "text-muted-foreground"}`}>
                            [{conversation.id.slice(0, 4).toUpperCase()}]
                          </div>
                          <div className="text-[8px] text-muted-foreground opacity-50 uppercase">
                            {conversation.timestamp}
                          </div>
                        </div>

                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className={`truncate text-[13px] font-medium tracking-tight ${
                              isActive ? "text-foreground" : "text-foreground/60"
                            }`}>
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
                            onDeleteConversation?.(conversation.id);
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
        </div>
      </div>
    </>
  );
}