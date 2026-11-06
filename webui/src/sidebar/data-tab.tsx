import { useState, useEffect, useCallback, useRef } from "react";
import { Loader2 } from "lucide-react";
import { WorkspaceTree } from "../files/workspace-tree.tsx";
import { EmptyState } from "../shared/empty-state.tsx";
import { api, type FileNode } from "../lib/api.ts";

interface DataTabProps {
  activeWorkspaceId: string | null;
  activeFilePath: string | null;
  onFileClick: (path: string) => void;
  tree: FileNode | null;
  treeWorkspaceId: string | null;
  onTreeUpdate: (tree: FileNode, fetchedFor: string) => void;
  onFileDeleted: (path: string) => void;
  onFileRenamed: (oldPath: string, newPath: string) => void;
  hasRepo: boolean;
}

export function DataTab({
  activeWorkspaceId,
  activeFilePath,
  onFileClick,
  tree,
  treeWorkspaceId,
  onTreeUpdate,
  onFileDeleted,
  onFileRenamed,
  hasRepo,
}: DataTabProps) {
  const [isLoading, setIsLoading] = useState(false);

  const activeWorkspaceIdRef = useRef(activeWorkspaceId);
  activeWorkspaceIdRef.current = activeWorkspaceId;

  const isTreeValid = !!tree && treeWorkspaceId === activeWorkspaceId;

  const refreshTree = useCallback(async () => {
    if (!activeWorkspaceId) return;
    const fetchedFor = activeWorkspaceId;
    try {
      const root = await api.getWorkspaceTree(fetchedFor);
      if (activeWorkspaceIdRef.current !== fetchedFor) return;
      onTreeUpdate(root, fetchedFor);
    } catch (err) {
      console.error("Failed to refresh workspace tree:", err);
    }
  }, [activeWorkspaceId, onTreeUpdate]);

  useEffect(() => {
    if (!activeWorkspaceId || isTreeValid) return;
    const fetchedFor = activeWorkspaceId;
    setIsLoading(true);
    api
      .getWorkspaceTree(fetchedFor)
      .then((root) => {
        if (activeWorkspaceIdRef.current !== fetchedFor) return;
        onTreeUpdate(root, fetchedFor);
      })
      .catch((err) => console.error("Failed to load workspace tree:", err))
      .finally(() => setIsLoading(false));
  }, [activeWorkspaceId, isTreeValid, onTreeUpdate]);

  if (!activeWorkspaceId) {
    return <EmptyState>Select a node to access data.</EmptyState>;
  }

  if (isLoading || !isTreeValid) {
    return (
      <div className="py-12 flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-primary/70" />
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
        hasRepo={hasRepo}
      />
    </div>
  );
}
