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
import { useChatFiles } from "./use-chat-files.ts";
import { useChatInput } from "./use-chat-input.ts";
import { useSidebar } from "../sidebar/use-sidebar.ts";
import { useWorkspaces } from "../sidebar/use-workspaces.ts";
import { usePreview } from "../files/use-preview.ts";
import { useConnectorDialog } from "../connectors/use-connector-dialog.ts";

export function ChatView() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const connectorDialog = useConnectorDialog();
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>();
  const [isCreateNodeOpen, setIsCreateNodeOpen] = useState(false);

  const conversations = useConversations();
  const sidebar = useSidebar();
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

  const messages = useMessages(currentConversationId, handleWorkspaceChange);
  const files = useChatFiles();

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
    setCurrentConversationId(id);
  }, [conversations.branchConversation]);

  const handleFileUploadClick = () => {
    fileInputRef.current?.click();
  };

  const showPreview = filePreview.filePath !== null;

  return (
    <div className="relative flex h-screen" style={{ background: "var(--color-background)" }}>
      <SidebarSegmentedControl
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        conversations={conversations.conversations}
        currentConversationId={currentConversationId}
        onConversationSelect={setCurrentConversationId}
        onNewConversation={async () => {
          const id = await conversations.createConversation(
            undefined,
            sidebar.activeWorkspaceId
          );
          setCurrentConversationId(id);
        }}
        onDeleteConversation={async (id) => {
          await conversations.deleteConversation(id);
          if (currentConversationId === id) setCurrentConversationId(undefined);
        }}
        isLoading={conversations.isLoading}
        activeTab={sidebar.activeTab}
        onTabChange={sidebar.setActiveTab}
        activeWorkspaceId={sidebar.activeWorkspaceId}
        onSelectWorkspace={workspaces.selectWorkspace}
        workspaceTree={workspaces.workspaceTree}
        treeWorkspaceId={workspaces.treeWorkspaceId}
        onWorkspaceTreeUpdate={workspaces.updateTree}
        activeFilePath={filePreview.filePath}
        onFileClick={filePreview.openFile}
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
            <div className="h-full overflow-hidden" style={{ flex: '2 2 0%', minWidth: 0 }}>
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
              />
            </div>
          )}

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
      className="sticky top-0 z-20 shrink-0 px-4 py-3 sm:px-6 overflow-hidden"
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
