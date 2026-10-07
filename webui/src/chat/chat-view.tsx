import { useState, useEffect, useRef, useCallback } from "react";
import { SidebarSegmentedControl } from "../sidebar/sidebar-segmented.tsx";
import { CreateNodeDialog } from "../connectors/create-node-dialog.tsx";
import { AddConnectorDialog } from "../connectors/add-connector-dialog.tsx";
import { Button } from "../ui/button.tsx";
import { MessagesList } from "./messages-list.tsx";
import { ChatInput } from "./chat-input.tsx";
import { Panel } from "../files/panel.tsx";
import { useConversations } from "./use-conversations.ts";
import { useMessages } from "./use-messages.ts";
import { useChatRoute } from "./use-chat-route.ts";
import { useChatFiles } from "./use-chat-files.ts";
import { useChatInput } from "./use-chat-input.ts";
import { useSidebar } from "../sidebar/use-sidebar.ts";
import { useWorkspaces } from "../sidebar/use-workspaces.ts";
import { usePreview } from "../files/use-preview.ts";
import { useConnectorDialog } from "../connectors/use-connector-dialog.ts";
import { useOverlayHistory, isDesktopViewport } from "../lib/use-overlay-history.ts";

export function ChatView() {
  const [sidebarOpen, setSidebarOpen] = useState(() => isDesktopViewport());
  const connectorDialog = useConnectorDialog();
  const { chatId, navigate } = useChatRoute();
  const currentConversationId = chatId ?? undefined;
  const [isCreateNodeOpen, setIsCreateNodeOpen] = useState(false);

  const closeSidebarOnMobile = useCallback(() => {
    if (!isDesktopViewport()) setSidebarOpen(false);
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const toggleSidebar = useCallback(() => setSidebarOpen((open) => !open), []);
  useOverlayHistory(sidebarOpen, toggleSidebar);

  const sidebar = useSidebar();
  const conversations = useConversations(sidebar.activeWorkspaceId);
  const workspaces = useWorkspaces(sidebar);
  const filePreview = usePreview(sidebar.activeWorkspaceId);

  const currentFilePathRef = useRef(filePreview.filePath);
  currentFilePathRef.current = filePreview.filePath;
  const refreshCurrentFileRef = useRef(filePreview.refreshCurrentFile);
  refreshCurrentFileRef.current = filePreview.refreshCurrentFile;

  const handleWorkspaceChange = useCallback(
    async (paths: string[]) => {
      await workspaces.refreshTree();
      const currentPath = currentFilePathRef.current;
      if (currentPath && paths.includes(currentPath)) {
        refreshCurrentFileRef.current();
      }
    },
    [workspaces.refreshTree]
  );

  const messages = useMessages(
    currentConversationId,
    handleWorkspaceChange,
    conversations.renameConversation
  );
  const files = useChatFiles();

  const loadedChat = messages.chat;
  const loadedChatId = loadedChat?.id;
  const loadedChatWorkspaceId = loadedChat?.workspace_id ?? null;
  const setActiveWorkspace = sidebar.setActiveWorkspace;
  useEffect(() => {
    if (!loadedChatId) return;
    setActiveWorkspace(loadedChatWorkspaceId);
  }, [loadedChatId, loadedChatWorkspaceId, setActiveWorkspace]);

  // When the active node changes (selected, toggled off, deleted, cleared),
  // drop the open session unless it belongs to the new node.
  const prevActiveWorkspaceRef = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    const prev = prevActiveWorkspaceRef.current;
    prevActiveWorkspaceRef.current = sidebar.activeWorkspaceId;
    if (prev === undefined || prev === sidebar.activeWorkspaceId) return;
    if (loadedChatId && loadedChatWorkspaceId !== sidebar.activeWorkspaceId) {
      navigate(null);
    }
  }, [sidebar.activeWorkspaceId, loadedChatId, loadedChatWorkspaceId, navigate]);

  const chatInList = conversations.conversations.some((c) => c.id === loadedChatId);
  const upsertConversation = conversations.upsertConversation;
  const activeWorkspaceId = sidebar.activeWorkspaceId;
  useEffect(() => {
    if (!loadedChat || chatInList) return;
    // Never inject a chat into a node-filtered list it doesn't belong to.
    if (loadedChatWorkspaceId !== activeWorkspaceId) return;
    upsertConversation(loadedChat);
  }, [loadedChat, chatInList, loadedChatWorkspaceId, activeWorkspaceId, upsertConversation]);

  useEffect(() => {
    if (!messages.loadError) return;
    if (messages.loadErrorStatus === 404 && chatId) {
      navigate(null, { replace: true });
    }
  }, [messages.loadError, messages.loadErrorStatus, chatId, navigate]);

  const currentConversation = conversations.conversations.find(
    (conv) => conv.id === currentConversationId
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (currentConversation?.title) {
      document.title = `${currentConversation.title} - Mikoshi Chat`;
    } else {
      document.title = "Mikoshi Chat";
    }
  }, [currentConversation?.title]);

  const chatInput = useChatInput({
    chatId: currentConversationId,
    onSend: messages.send,
    onEdit: messages.edit,
    messages: messages.messages,
    getFiles: () => files.getAllFiles(),
    isSending: messages.isSending,
    onSendComplete: () => {
      files.clearAll();
      conversations.refresh();
    },
    onEditComplete: () => {
      conversations.refresh();
    },
  });

  const currentConversationIdRef = useRef(currentConversationId);
  currentConversationIdRef.current = currentConversationId;

  const handleRetry = useCallback(async () => {
    await messages.retry();
    conversations.refresh();
  }, [messages.retry, conversations.refresh]);

  const handleBranch = useCallback(async (messageId: string) => {
    const id = await conversations.branchConversation(currentConversationIdRef.current!, messageId);
    navigate(id);
  }, [conversations.branchConversation, navigate]);

  const handleFileUploadClick = () => {
    fileInputRef.current?.click();
  };

  const showPreview = filePreview.filePath !== null;
  const [chatHidden, setChatHidden] = useState(false);
  useOverlayHistory(showPreview, filePreview.closePreview);

  useEffect(() => {
    if (!showPreview) setChatHidden(false);
  }, [showPreview]);

  return (
    <div className="relative flex h-dvh" style={{ background: "var(--color-background)" }}>
      <SidebarSegmentedControl
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
        conversations={conversations.conversations}
        currentConversationId={currentConversationId}
        onConversationSelect={(id) => {
          navigate(id);
          closeSidebarOnMobile();
        }}
        onNewConversation={async () => {
          const id = await conversations.createConversation(
            undefined,
            sidebar.activeWorkspaceId
          );
          navigate(id);
          closeSidebarOnMobile();
        }}
        onDeleteConversation={async (id) => {
          await conversations.deleteConversation(id);
          if (chatId === id) navigate(null, { replace: true });
        }}
        hasMore={conversations.hasMore}
        onLoadMore={conversations.loadMore}
        isLoading={conversations.isLoading}
        activeTab={sidebar.activeTab}
        onTabChange={sidebar.setActiveTab}
        activeWorkspaceId={sidebar.activeWorkspaceId}
        onSelectWorkspace={(id) => {
          workspaces.selectWorkspace(id);
          closeSidebarOnMobile();
        }}
        workspaceTree={workspaces.workspaceTree}
        treeWorkspaceId={workspaces.treeWorkspaceId}
        onWorkspaceTreeUpdate={workspaces.updateTree}
        activeFilePath={filePreview.filePath}
        onFileClick={(path) => {
          filePreview.openFile(path);
          closeSidebarOnMobile();
        }}
        onFileDeleted={filePreview.handleFileDeleted}
        onFileRenamed={filePreview.handleFileRenamed}
        activeWorkspaceHasRepo={workspaces.activeWorkspaceHasRepo}
        onNewWorkspace={() => setIsCreateNodeOpen(true)}
        onDeleteWorkspace={async (id) => {
          await workspaces.deleteWorkspace(id);
          conversations.refresh();
        }}
        onClearFilter={() => {
          workspaces.clearFilter();
          filePreview.closePreview();
        }}
        workspaces={workspaces.workspaces}
        workspacesLoading={workspaces.workspacesLoading}
      />

      <div className="relative flex flex-col flex-1 min-w-0">
        <ChatHeader
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(true)}
          chatTitle={currentConversation?.title}
        />

        <div className="flex flex-1 min-h-0">
          {showPreview && (
            <div
              className="fixed inset-0 z-40 bg-background lg:relative lg:inset-auto lg:z-auto lg:h-full lg:overflow-hidden"
              style={{ flex: "2 2 0%", minWidth: 0 }}
            >
              <Panel
                filePath={filePreview.filePath}
                fileContent={filePreview.fileContent}
                isLoading={filePreview.isLoading}
                onClose={filePreview.closePreview}
                workspaceId={sidebar.activeWorkspaceId}
                fileIndex={workspaces.fileIndex}
                onFileClick={filePreview.openFile}
                mode={filePreview.mode}
                setMode={filePreview.setMode}
                editContent={filePreview.editContent}
                setEditContent={filePreview.setEditContent}
                isDirty={filePreview.isDirty}
                isSaving={filePreview.isSaving}
                onSave={filePreview.saveFile}
                chatHidden={chatHidden}
                onToggleChat={() => setChatHidden((hidden) => !hidden)}
              />
            </div>
          )}

          {!chatHidden && (
          <div className="flex flex-col flex-1 min-w-0">
            <MessagesList
              messages={messages.messages}
              isLoading={messages.isLoading}
              isSending={messages.isSending}
              loadError={messages.loadError}
              currentConversationId={currentConversationId}
              messagesEndRef={messagesEndRef}
              pendingApprovals={messages.pendingApprovals}
              onApprove={messages.approveApproval}
              onDeny={messages.denyApproval}
              onBranch={handleBranch}
              onRetry={handleRetry}
              onEdit={chatInput.handleEdit}
            />

            <ChatInput
              inputValue={chatInput.inputValue}
              isEditingMode={chatInput.isEditingMode}
              onInputChange={chatInput.setInputValue}
              onCancelEdit={chatInput.cancelEdit}
              onSend={chatInput.handleSend}
              onKeyDown={chatInput.handleKeyDown}
              isSending={messages.isSending}
              isUploadingFiles={files.isUploading}
              currentConversationId={currentConversationId}
              chatSettings={messages.chatSettings}
              onSettingsChange={messages.setChatSettings}
              uploadedFiles={files.uploadedFiles}
              connectorEntries={files.connectorEntries}
              onRemoveFile={files.removeFile}
              onRemoveConnectorEntry={files.removeConnectorEntry}
              onEditConnectorEntry={(connectorId, resourceId) => {
                const entry = files.connectorEntries.find(
                  (e) => e.connectorId === connectorId && e.resourceId === resourceId
                );
                if (entry) {
                  connectorDialog.openEdit(entry);
                }
              }}
              onFileUploadClick={handleFileUploadClick}
              onConnectorDialogOpen={connectorDialog.openNew}
              onChatUpdated={conversations.refresh}
              textareaRef={chatInput.textareaRef}
              fileInputRef={fileInputRef}
              onFileChange={(e) => {
                if (e.target.files) files.uploadFiles(Array.from(e.target.files));
              }}
              workspaceFiles={Array.from(workspaces.fileIndex.values())}
              hasWorkspace={!!sidebar.activeWorkspaceId}
            />
          </div>
          )}
        </div>
      </div>

      <AddConnectorDialog
        open={connectorDialog.isOpen}
        onOpenChange={connectorDialog.handleOpenChange}
        chatId={currentConversationId}
        editingEntry={connectorDialog.editingEntry ?? undefined}
        onFilesAdded={(entry) => {
          if (connectorDialog.editingEntry) {
            files.updateConnectorEntry(
              connectorDialog.editingEntry.connectorId,
              connectorDialog.editingEntry.resourceId,
              entry
            );
          } else {
            files.addConnectorEntry(entry);
          }
        }}
      />

      <CreateNodeDialog
        open={isCreateNodeOpen}
        onOpenChange={setIsCreateNodeOpen}
        onCreated={workspaces.workspaceCreated}
      />
    </div>
  );
}

function ChatHeader({ sidebarOpen, onToggleSidebar, chatTitle }: {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  chatTitle?: string;
}) {
  return (
    <div
      className="sticky top-0 z-20 shrink-0 px-4 py-3 cp-safe-top sm:px-6 overflow-hidden"
      style={{
        background: "linear-gradient(180deg, rgb(var(--cp-rgb-surface3) / 0.95) 0%, rgb(var(--cp-rgb-surface3) / 0.8) 100%)",
        backdropFilter: "blur(8px)",
        borderBottom: "1px solid rgb(var(--cp-rgb-yellow) / 0.15)",
      }}
    >
      <div className="flex items-center gap-3">
        {!sidebarOpen && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleSidebar}
            className="h-8 w-8 shrink-0"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect width="18" height="18" x="3" y="3" />
              <path d="M9 3v18" />
            </svg>
            <span className="sr-only">Open sidebar</span>
          </Button>
        )}
        <div className="flex flex-col min-w-0 flex-1">
          <h1
            className="text-sm font-bold text-primary uppercase tracking-[0.15em]"
            style={{ fontSize: '16px' }}
          >
            Mikoshi
          </h1>
          {chatTitle && (
            <p className="cp-label text-muted-foreground truncate mt-0.5">
              {chatTitle}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5" style={{ animation: 'cp-status-glow 2s ease-in-out infinite' }}>
          <div className="relative w-2.5 h-2.5">
            <div className="absolute inset-0 bg-cp-cyan-bright cp-diamond" />
            <div className="absolute inset-0 bg-cp-cyan-bright cp-diamond" style={{ animation: 'cp-blink 1.5s ease-in-out infinite' }} />
          </div>
          <span className="cp-label text-cp-cyan-bright/70">SYS</span>
          <span className="cp-label text-cp-cyan-bright/40">:</span>
          <span className="cp-label text-cp-cyan-bright/70">OK</span>
        </div>
      </div>
      <div className="h-[2px] mt-2 bg-gradient-to-r from-primary/40 via-primary/10 to-transparent" />
    </div>
  );
}
