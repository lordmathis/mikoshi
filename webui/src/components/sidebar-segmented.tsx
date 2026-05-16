import { PanelLeftClose } from "lucide-react";
import { Button } from "./ui/button";
import { SessionsTab } from "./sessions-tab";
import { NodesTab } from "./nodes-tab";
import { DataTab } from "./data-tab";
import { type Conversation } from "./sidebar";
import { type FileNode } from "../lib/api";

type SidebarTab = "sessions" | "nodes" | "data";

interface SidebarSegmentedControlProps {
  isOpen: boolean;
  onToggle: () => void;
  conversations: Conversation[];
  currentConversationId?: string;
  onConversationSelect: (conversationId: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (conversationId: string) => void;
  isLoading?: boolean;

  activeTab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  activeWorkspaceId: string | null;
  onSelectWorkspace: (id: string | null) => void;

  workspaceTree: FileNode | null;
  onWorkspaceTreeUpdate: (tree: FileNode) => void;
  activeFilePath: string | null;
  onFileClick: (path: string) => void;
  onFileDeleted: (path: string) => void;
  onFileRenamed: (oldPath: string, newPath: string) => void;

  onNewWorkspace: () => void;
  onDeleteWorkspace: (id: string) => void;
  onClearFilter: () => void;
  workspaces: { id: string; name: string }[];
  workspacesLoading?: boolean;
}

const tabs: { key: SidebarTab; label: string }[] = [
  { key: "sessions", label: "Sessions" },
  { key: "nodes", label: "Nodes" },
  { key: "data", label: "Data" },
];

export function SidebarSegmentedControl({
  isOpen,
  onToggle,
  conversations,
  currentConversationId,
  onConversationSelect,
  onNewConversation,
  onDeleteConversation,
  isLoading,

  activeTab,
  onTabChange,
  activeWorkspaceId,
  onSelectWorkspace,

  workspaceTree,
  onWorkspaceTreeUpdate,
  activeFilePath,
  onFileClick,
  onFileDeleted,
  onFileRenamed,

  onNewWorkspace,
  onDeleteWorkspace,
  onClearFilter,
  workspaces,
  workspacesLoading,
}: SidebarSegmentedControlProps) {
  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-background/80 backdrop-blur-sm lg:hidden"
          onClick={onToggle}
        />
      )}

      <div
        className={`fixed left-0 top-0 z-40 h-screen w-[290px] transform border-r bg-background/95 backdrop-blur-md transition-transform duration-200 ease-in-out lg:relative lg:z-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0 lg:w-0 lg:border-0"
        }`}
        style={{ borderRightColor: "rgb(var(--cp-rgb-yellow) / 0.1)" }}
      >
        <div className={`flex h-full flex-col overflow-hidden ${isOpen ? "" : "lg:hidden"}`}>
          <div className="flex shrink-0 items-center justify-between px-4 py-4 border-b border-white/5">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-primary rotate-45" />
              <h2 className="text-[10px] font-black text-primary uppercase tracking-[0.25em]">
                Mikoshi
              </h2>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggle}
              className="h-7 w-7 opacity-50 hover:opacity-100"
            >
              <PanelLeftClose className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex shrink-0 border-b border-white/5">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                className={`flex-1 py-2.5 text-[10px] font-black uppercase tracking-[0.2em] transition-colors ${
                  activeTab === tab.key
                    ? "text-primary border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => onTabChange(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {activeTab === "sessions" && (
              <SessionsTab
                conversations={conversations}
                currentConversationId={currentConversationId}
                activeWorkspaceId={activeWorkspaceId}
                workspaces={workspaces}
                onConversationSelect={onConversationSelect}
                onNewConversation={onNewConversation}
                onDeleteConversation={onDeleteConversation}
                onClearFilter={onClearFilter}
                isLoading={isLoading}
              />
            )}
            {activeTab === "nodes" && (
              <NodesTab
                activeWorkspaceId={activeWorkspaceId}
                workspaces={workspaces}
                isLoading={!!workspacesLoading}
                onSelectWorkspace={onSelectWorkspace}
                onNewWorkspace={onNewWorkspace}
                onDeleteWorkspace={onDeleteWorkspace}
              />
            )}
            {activeTab === "data" && (
              <DataTab
                activeWorkspaceId={activeWorkspaceId}
                activeFilePath={activeFilePath}
                onFileClick={onFileClick}
                tree={workspaceTree}
                onTreeUpdate={onWorkspaceTreeUpdate}
                onFileDeleted={onFileDeleted}
                onFileRenamed={onFileRenamed}
              />
            )}
          </div>
        </div>
      </div>
    </>
  );
}
