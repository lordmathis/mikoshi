import { Plus } from "lucide-react";
import { Button } from "./ui/button";
import { SidebarItem } from "./sidebar-item";

interface NodesTabProps {
  activeWorkspaceId: string | null;
  workspaces: { id: string; name: string }[];
  isLoading: boolean;
  onSelectWorkspace: (id: string | null) => void;
  onNewWorkspace: () => void;
  onDeleteWorkspace: (id: string) => void;
}

export function NodesTab({
  activeWorkspaceId,
  workspaces,
  isLoading,
  onSelectWorkspace,
  onNewWorkspace,
  onDeleteWorkspace,
}: NodesTabProps) {

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
              <SidebarItem
                key={ws.id}
                id={ws.id}
                isActive={isActive}
                label={ws.name}
                sublabel={`[${ws.id.slice(0, 4).toUpperCase()}]`}
                confirmMessage={`Delete node "${ws.name}" and all linked sessions?`}
                onClick={() => onSelectWorkspace(isActive ? null : ws.id)}
                onDelete={() => onDeleteWorkspace(ws.id)}
              />
            );
          })
        )}
      </div>
    </>
  );
}
