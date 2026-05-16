import { useState, useCallback, useRef } from "react";
import { api } from "../lib/api";

export function useFilePreview(workspaceId: string | null) {
  const [filePath, setFilePath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setModeState] = useState<"preview" | "edit">("preview");
  const [editContent, setEditContent] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const modeRef = useRef(mode);
  const editContentRef = useRef(editContent);
  const filePathRef = useRef(filePath);
  const isSavingRef = useRef(isSaving);

  modeRef.current = mode;
  editContentRef.current = editContent;
  filePathRef.current = filePath;
  isSavingRef.current = isSaving;

  const setMode = useCallback((m: "preview" | "edit") => {
    modeRef.current = m;
    setModeState(m);
  }, []);

  const isDirty = editContent !== null && editContent !== fileContent;

  const openFile = useCallback(async (path: string) => {
    if (!workspaceId) return;
    setFilePath(path);
    filePathRef.current = path;
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
    if (!workspaceId || !filePathRef.current) return;
    try {
      const content = await api.getWorkspaceFile(workspaceId, filePathRef.current);
      setFileContent(content);
    } catch {}
  }, [workspaceId]);

  const saveFile = useCallback(async () => {
    if (!workspaceId || !filePathRef.current || editContentRef.current === null || isSavingRef.current) return;
    setIsSaving(true);
    try {
      await api.writeWorkspaceFile(workspaceId, filePathRef.current, editContentRef.current);
      const content = await api.getWorkspaceFile(workspaceId, filePathRef.current);
      setFileContent(content);
      setEditContent(content);
    } catch (error) {
      console.error("Failed to save file:", error);
    } finally {
      setIsSaving(false);
    }
  }, [workspaceId]);

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
