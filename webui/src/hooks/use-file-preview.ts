import { useState, useCallback } from "react";
import { api } from "../lib/api";

export function useFilePreview(workspaceId: string | null) {
  const [filePath, setFilePath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const openFile = useCallback(async (path: string) => {
    if (!workspaceId) return;
    setFilePath(path);
    setFileContent(null);
    setIsLoading(true);
    try {
      const content = await api.getWorkspaceFile(workspaceId, path);
      setFileContent(content);
    } catch (error) {
      console.error("Failed to fetch workspace file:", error);
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  const refreshCurrentFile = useCallback(async () => {
    if (!workspaceId || !filePath) return;
    try {
      const content = await api.getWorkspaceFile(workspaceId, filePath);
      setFileContent(content);
    } catch {}
  }, [workspaceId, filePath]);

  const closePreview = useCallback(() => {
    setFilePath(null);
    setFileContent(null);
  }, []);

  return {
    filePath,
    fileContent,
    isLoading,
    openFile,
    refreshCurrentFile,
    closePreview,
  };
}
