import { useState, useEffect, useCallback, useRef } from "react";
import { api, type FileNode } from "../lib/api.ts";
import { useSidebar } from "./use-sidebar.ts";

type SidebarApi = ReturnType<typeof useSidebar>;

interface WorkspaceSummary {
  id: string;
  name: string;
  repo_url: string | null;
}

export function useWorkspaces(sidebar: SidebarApi) {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [workspaceTree, setWorkspaceTree] = useState<FileNode | null>(null);
  const [treeWorkspaceId, setTreeWorkspaceId] = useState<string | null>(null);
  const [fileIndex, setFileIndex] = useState<Map<string, string>>(new Map());

  const activeWorkspaceIdRef = useRef(sidebar.activeWorkspaceId);
  activeWorkspaceIdRef.current = sidebar.activeWorkspaceId;

  useEffect(() => {
    setWorkspacesLoading(true);
    api.listWorkspaces().then((res) => {
      setWorkspaces(res.workspaces.map((w) => ({ id: w.id, name: w.name, repo_url: w.repo_url })));
    }).catch(() => {}).finally(() => setWorkspacesLoading(false));
  }, [refreshTrigger]);

  useEffect(() => {
    if (!sidebar.activeWorkspaceId) {
      setFileIndex(new Map());
      return;
    }
    api.getWorkspaceFileList(sidebar.activeWorkspaceId).then((files) => {
      const index = new Map<string, string>();
      for (const filePath of files) {
        const fileName = filePath.split("/").pop()!;
        const key = fileName.toLowerCase();
        if (!index.has(key)) {
          index.set(key, filePath);
        }
      }
      setFileIndex(index);
    }).catch(() => {});
  }, [sidebar.activeWorkspaceId]);

  const refresh = useCallback(() => {
    setRefreshTrigger((n) => n + 1);
  }, []);

  const resetTree = useCallback(() => {
    setWorkspaceTree(null);
    setTreeWorkspaceId(null);
  }, []);

  const refreshTree = useCallback(async () => {
    const wsId = activeWorkspaceIdRef.current;
    if (!wsId) return;
    try {
      const tree = await api.getWorkspaceTree(wsId);
      setWorkspaceTree(tree);
      setTreeWorkspaceId(wsId);
    } catch {}
  }, []);

  const updateTree = useCallback((tree: FileNode) => {
    setWorkspaceTree(tree);
    setTreeWorkspaceId(activeWorkspaceIdRef.current);
  }, []);

  const selectWorkspace = useCallback((id: string | null) => {
    sidebar.setActiveWorkspace(id);
    if (id) {
      sidebar.setActiveTab("data");
    }
  }, [sidebar]);

  const workspaceCreated = useCallback((ws: { id: string }) => {
    refresh();
    selectWorkspace(ws.id);
  }, [refresh, selectWorkspace]);

  const deleteWorkspace = useCallback(async (id: string) => {
    await api.deleteWorkspace(id);
    refresh();
    if (activeWorkspaceIdRef.current === id) {
      sidebar.setActiveWorkspace(null);
      resetTree();
    }
  }, [refresh, resetTree, sidebar]);

  const clearFilter = useCallback(() => {
    sidebar.setActiveWorkspace(null);
    resetTree();
  }, [resetTree, sidebar]);

  const activeWorkspaceHasRepo = !!workspaces.find(
    (w) => w.id === sidebar.activeWorkspaceId
  )?.repo_url;

  return {
    workspaces,
    workspacesLoading,
    workspaceTree,
    treeWorkspaceId,
    fileIndex,
    activeWorkspaceHasRepo,
    refresh,
    refreshTree,
    updateTree,
    selectWorkspace,
    workspaceCreated,
    deleteWorkspace,
    clearFilter,
  };
}
