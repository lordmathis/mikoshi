import { useState, useEffect, useCallback } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import { api, type Workspace } from "../lib/api";

interface NodesTabProps {
  activeWorkspaceId: string | null;
  onSelectWorkspace: (id: string | null) => void;
  onNewWorkspace: () => void;
  onDeleteWorkspace: (id: string) => void;
  refreshTrigger?: number;
}

export function NodesTab({
  activeWorkspaceId,
  onSelectWorkspace,
  onNewWorkspace,
  onDeleteWorkspace,
  refreshTrigger,
}: NodesTabProps) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchWorkspaces = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await api.listWorkspaces();
      setWorkspaces(res.workspaces);
    } catch (error) {
      console.error("Failed to fetch workspaces:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces, refreshTrigger]);

  return (
    <>
      <div className="px-3 py-3">
        <Button
          variant="outline"
          className="w-full justify-between gap-2 text-[14px] h-10 border-primary/20 hover:border-primary/50 bg-primary/5 group text-cyan"
          onClick={onNewWorkspace}
        >
          <span className="flex items-center gap-2">
            <Plus className="h-3.5 w-3.5" />
            SPAWN_NODE
          </span>
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-6 space-y-2">
        {isLoading ? (
          <div className="py-12 text-center cp-label opacity-40 animate-pulse">
            Syncing...
          </div>
        ) : workspaces.length === 0 ? (
          <div className="py-12 text-center cp-label opacity-20 italic">
            No nodes found
          </div>
        ) : (
          workspaces.map((ws) => {
            const isActive = activeWorkspaceId === ws.id;
            return (
              <div
                key={ws.id}
                className={`group relative flex items-center transition-all duration-200 cursor-pointer border ${
                  isActive
                    ? "bg-primary/5 border-primary/30 shadow-[0_0_15px_rgba(245,216,0,0.05)]"
                    : "bg-white/[0.02] border-white/5 hover:border-white/10 hover:bg-white/[0.04]"
                }`}
                style={{
                  clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%)",
                }}
                onClick={() => onSelectWorkspace(isActive ? null : ws.id)}
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
                      [{ws.id.slice(0, 4).toUpperCase()}]
                    </div>
                  </div>
                  <div
                    className={`truncate text-[13px] font-medium tracking-tight ${
                      isActive ? "text-foreground" : "text-foreground/60"
                    }`}
                  >
                    {ws.name}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 mr-2 opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(`Delete node "${ws.name}" and all linked sessions?`)) {
                      onDeleteWorkspace(ws.id);
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            );
          })
        )}
      </div>
    </>
  );
}
