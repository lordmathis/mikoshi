import { useState, useCallback } from "react";

const TABS = ["sessions", "nodes", "data"] as const;
type SidebarTab = (typeof TABS)[number];

interface SidebarState {
  activeTab: SidebarTab;
  activeWorkspaceId: string | null;
}

function isSidebarTab(value: unknown): value is SidebarTab {
  return typeof value === "string" && (TABS as readonly string[]).includes(value);
}

function loadState(): SidebarState {
  try {
    const raw = localStorage.getItem("mikoshi-sidebar");
    if (raw) {
      const parsed: unknown = JSON.parse(raw);
      if (typeof parsed === "object" && parsed !== null) {
        const stored = parsed as Record<string, unknown>;
        return {
          activeTab: isSidebarTab(stored.activeTab) ? stored.activeTab : "sessions",
          activeWorkspaceId:
            typeof stored.activeWorkspaceId === "string" ? stored.activeWorkspaceId : null,
        };
      }
    }
  } catch {}
  return { activeTab: "sessions", activeWorkspaceId: null };
}

function saveState(state: SidebarState) {
  try {
    localStorage.setItem("mikoshi-sidebar", JSON.stringify(state));
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
