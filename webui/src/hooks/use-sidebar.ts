import { useState, useCallback } from "react";

type SidebarTab = "sessions" | "nodes" | "data";

interface SidebarState {
  activeTab: SidebarTab;
  activeWorkspaceId: string | null;
}

function loadState(): SidebarState {
  try {
    const raw = sessionStorage.getItem("mikoshi-sidebar");
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        activeTab: parsed.activeTab || "sessions",
        activeWorkspaceId: parsed.activeWorkspaceId || null,
      };
    }
  } catch {}
  return { activeTab: "sessions", activeWorkspaceId: null };
}

function saveState(state: SidebarState) {
  try {
    sessionStorage.setItem("mikoshi-sidebar", JSON.stringify(state));
  } catch {}
}

export function useSidebar() {
  const [state, setState] = useState<SidebarState>(loadState);

  const setActiveTab = useCallback((tab: SidebarTab) => {
    setState((prev) => {
      const next = { ...prev, activeTab: tab };
      saveState(next);
      return next;
    });
  }, []);

  const setActiveWorkspace = useCallback((id: string | null) => {
    setState((prev) => {
      const next = { ...prev, activeWorkspaceId: id };
      saveState(next);
      return next;
    });
  }, []);

  return {
    activeTab: state.activeTab,
    activeWorkspaceId: state.activeWorkspaceId,
    setActiveTab,
    setActiveWorkspace,
  };
}
