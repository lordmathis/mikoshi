import { useState, useCallback, useRef } from "react";
import { api } from "../lib/api";

export function useFilePreview(workspaceId: string | null) {
  const [filePath, setFilePath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setModeState] = useState<"preview" | "edit">("preview");
  const modeRef = useRef(mode);
  const setMode = useCallback((m: "preview" | "edit") => {
    modeRef.current = m;
    setModeState(m);
  }, []);
  const [editContent, setEditContent] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const isDirty = editContent !== null && editContent !== fileContent;

  const openFile = useCallback(async (path: string) => {
    if (!workspaceId) return;
    setFilePath(path);
    setFileContent(null);
    setIsLoading(true);
    setEditContent(null);
    try {
      const content = await api.getWorkspaceFile(workspaceId, path);
      setFileContent(content);
      if (modeRef.current === "edit") {
        setEditContent(content);
      }
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

  const saveFile = useCallback(async () => {
    if (!workspaceId || !filePath || editContent === null || isSaving) return;
    setIsSaving(true);
    try {
      await api.writeWorkspaceFile(workspaceId, filePath, editContent);
      const content = await api.getWorkspaceFile(workspaceId, filePath);
      setFileContent(content);
      setEditContent(content);
    } catch (error) {
      console.error("Failed to save file:", error);
    } finally {
      setIsSaving(false);
    }
  }, [workspaceId, filePath, editContent, isSaving]);

  const closePreview = useCallback(() => {
    setFilePath(null);
    setFileContent(null);
    setMode("preview");
    setEditContent(null);
  }, []);

  return {
    filePath,
    fileContent,
    isLoading,
    openFile,
    refreshCurrentFile,
    closePreview,
    mode,
    setMode,
    editContent,
    setEditContent,
    isDirty,
    isSaving,
    saveFile,
  };
}
