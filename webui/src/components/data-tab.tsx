import { useState, useEffect, useCallback } from "react";
import { Loader2 } from "lucide-react";
import { WorkspaceTree } from "./workspace-tree";
import { api, type FileNode } from "../lib/api";

interface DataTabProps {
  activeWorkspaceId: string | null;
  activeFilePath: string | null;
  onFileClick: (path: string) => void;
  tree: FileNode | null;
  onTreeUpdate: (tree: FileNode) => void;
  onFileDeleted: (path: string) => void;
  onFileRenamed: (oldPath: string, newPath: string) => void;
}

export function DataTab({
  activeWorkspaceId,
  activeFilePath,
  onFileClick,
  tree,
  onTreeUpdate,
  onFileDeleted,
  onFileRenamed,
}: DataTabProps) {
  const [isLoading, setIsLoading] = useState(false);

  const refreshTree = useCallback(async () => {
    if (!activeWorkspaceId) return;
    try {
      const root = await api.getWorkspaceTree(activeWorkspaceId);
      onTreeUpdate(root);
    } catch (err) {
      console.error("Failed to refresh workspace tree:", err);
    }
  }, [activeWorkspaceId, onTreeUpdate]);

  useEffect(() => {
    if (!activeWorkspaceId) return;
    setIsLoading(true);
    api
      .getWorkspaceTree(activeWorkspaceId)
      .then((root) => onTreeUpdate(root))
      .catch((err) => console.error("Failed to load workspace tree:", err))
      .finally(() => setIsLoading(false));
  }, [activeWorkspaceId, onTreeUpdate]);

  if (!activeWorkspaceId) {
    return (
      <div className="py-12 text-center cp-label opacity-20 italic">
        Select a node to access data.
      </div>
    );
  }

  if (isLoading && !tree) {
    return (
      <div className="py-12 flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-primary/50" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-3 pb-6">
      <WorkspaceTree
        tree={tree}
        activeFilePath={activeFilePath}
        onFileClick={onFileClick}
        workspaceId={activeWorkspaceId}
        onRefreshTree={refreshTree}
        onFileDeleted={onFileDeleted}
        onFileRenamed={onFileRenamed}
      />
    </div>
  );
}
