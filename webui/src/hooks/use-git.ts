import { useState, useEffect, useCallback } from "react";
import { api, type GitStatus, type GitResult } from "../lib/api";

export function useGit(workspaceId: string | null) {
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const s = await api.gitStatus(workspaceId);
      setStatus(s);
    } catch {
      setStatus(null);
    }
  }, [workspaceId]);

  useEffect(() => {
    if (workspaceId) {
      refresh();
    } else {
      setStatus(null);
    }
  }, [workspaceId, refresh]);

  const commit = useCallback(
    async (message: string): Promise<GitResult> => {
      if (!workspaceId) return { success: false, output: "No workspace" };
      setIsLoading(true);
      try {
        const result = await api.gitCommit(workspaceId, message);
        await refresh();
        return result;
      } finally {
        setIsLoading(false);
      }
    },
    [workspaceId, refresh]
  );

  const pull = useCallback(async (): Promise<GitResult> => {
    if (!workspaceId) return { success: false, output: "No workspace" };
    setIsLoading(true);
    try {
      const result = await api.gitPull(workspaceId);
      await refresh();
      return result;
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId, refresh]);

  const push = useCallback(async (): Promise<GitResult> => {
    if (!workspaceId) return { success: false, output: "No workspace" };
    setIsLoading(true);
    try {
      const result = await api.gitPush(workspaceId);
      await refresh();
      return result;
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId, refresh]);

  return { status, isLoading, commit, pull, push, refresh };
}
