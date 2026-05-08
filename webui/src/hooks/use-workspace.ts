import { useState, useCallback, useRef } from "react";
import { api, type FileNode, type WorkspaceUpdateData } from "../lib/api";

export function useWorkspace(workspaceId: string | null | undefined) {
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [tree, setTree] = useState<FileNode | null>(null);
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const treeCache = useRef<Map<string, FileNode>>(new Map());

  const fetchTree = useCallback(
    async (path?: string) => {
      if (!workspaceId) return;
      try {
        const node = await api.getWorkspaceTree(workspaceId, path ?? "");
        if (!path) {
          setTree(node);
        }
        treeCache.current.set(path ?? "", node);
        return node;
      } catch (error) {
        console.error("Failed to fetch workspace tree:", error);
      }
    },
    [workspaceId]
  );

  const fetchFile = useCallback(
    async (path: string) => {
      if (!workspaceId) return;
      try {
        setIsLoadingFile(true);
        const content = await api.getWorkspaceFile(workspaceId, path);
        setFileContent(content);
        setActiveFilePath(path);
      } catch (error) {
        console.error("Failed to fetch workspace file:", error);
      } finally {
        setIsLoadingFile(false);
      }
    },
    [workspaceId]
  );

  const handleSSEEvent = useCallback(
    (data: WorkspaceUpdateData) => {
      if (workspaceId && data.workspace_id === workspaceId) {
        setTree(data.tree);
      }
    },
    [workspaceId]
  );

  const reset = useCallback(() => {
    setActiveFilePath(null);
    setFileContent(null);
    setTree(null);
    treeCache.current.clear();
  }, []);

  const closeFile = useCallback(() => {
    setActiveFilePath(null);
    setFileContent(null);
  }, []);

  return {
    activeFilePath,
    fileContent,
    tree,
    isLoadingFile,
    fetchTree,
    fetchFile,
    handleSSEEvent,
    reset,
    closeFile,
  };
}
