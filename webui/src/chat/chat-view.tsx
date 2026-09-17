import { useState, useEffect, useRef, useCallback } from "react";
import { SidebarSegmentedControl } from "../sidebar/sidebar-segmented.tsx";
import { CreateNodeDialog } from "../connectors/create-node-dialog.tsx";
import { AddConnectorDialog } from "../connectors/add-connector-dialog.tsx";
import { ChatHeader } from "./chat-header.tsx";
import { MessagesList } from "./messages-list.tsx";
import { ChatInput } from "./chat-input.tsx";
import { Panel } from "../files/panel.tsx";
import { useConversations } from "./use-conversations.ts";
import { useMessages } from "./use-messages.ts";
import { useChatFiles } from "./use-chat-files.ts";
import { useChatInput } from "./use-chat-input.ts";
import { useSidebar } from "../sidebar/use-sidebar.ts";
import { usePreview } from "../files/use-preview.ts";
import { useConnectorDialog } from "../connectors/use-connector-dialog.ts";
import { api, type FileNode } from "../lib/api.ts";

export function ChatView() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const connectorDialog = useConnectorDialog();
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>();
  const [isCreateNodeOpen, setIsCreateNodeOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<{ id: string; name: string; repo_url: string | null }[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(true);
  const [workspaceRefreshTrigger, setWorkspaceRefreshTrigger] = useState(0);
  const [sidebarWorkspaceTree, setSidebarWorkspaceTree] = useState<FileNode | null>(null);
  const [treeWorkspaceId, setTreeWorkspaceId] = useState<string | null>(null);
  const [fileIndex, setFileIndex] = useState<Map<string, string>>(new Map());

  const conversations = useConversations();
  const sidebar = useSidebar();
  const filePreview = usePreview(sidebar.activeWorkspaceId);

  const activeWorkspaceIdRef = useRef(sidebar.activeWorkspaceId);
  activeWorkspaceIdRef.current = sidebar.activeWorkspaceId;
  const currentFilePathRef = useRef(filePreview.filePath);
  currentFilePathRef.current = filePreview.filePath;
  const refreshCurrentFileRef = useRef(filePreview.refreshCurrentFile);
  refreshCurrentFileRef.current = filePreview.refreshCurrentFile;

  const handleWorkspaceChange = useCallback(
    async (paths: string[]) => {
      const wsId = activeWorkspaceIdRef.current;
      if (!wsId) return;

      try {
        const tree = await api.getWorkspaceTree(wsId);
        setSidebarWorkspaceTree(tree);
        setTreeWorkspaceId(wsId);
      } catch {}

      const currentPath = currentFilePathRef.current;
      if (currentPath && paths.includes(currentPath)) {
        refreshCurrentFileRef.current();
      }
    },
    []
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

  useEffect(() => {
    setWorkspacesLoading(true);
    api.listWorkspaces().then((res) => {
      setWorkspaces(res.workspaces.map((w) => ({ id: w.id, name: w.name, repo_url: w.repo_url })));
    }).catch(() => {}).finally(() => setWorkspacesLoading(false));
  }, [workspaceRefreshTrigger]);

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

  const handleNewWorkspace = () => {
    setIsCreateNodeOpen(true);
  };

  const handleDeleteWorkspace = async (id: string) => {
    await api.deleteWorkspace(id);
    setWorkspaceRefreshTrigger((n) => n + 1);
    if (sidebar.activeWorkspaceId === id) {
      sidebar.setActiveWorkspace(null);
      setSidebarWorkspaceTree(null);
      setTreeWorkspaceId(null);
    }
    conversations.refresh();
  };

  const handleWorkspaceCreated = (ws: { id: string; name: string }) => {
    setWorkspaceRefreshTrigger((n) => n + 1);
    sidebar.setActiveWorkspace(ws.id);
    sidebar.setActiveTab("data");
  };

  const handleSelectWorkspace = (id: string | null) => {
    sidebar.setActiveWorkspace(id);
    if (id) {
      sidebar.setActiveTab("data");
    }
  };

  const handleSidebarTreeUpdate = useCallback((tree: FileNode) => {
    setSidebarWorkspaceTree(tree);
    setTreeWorkspaceId(activeWorkspaceIdRef.current);
  }, []);

  const showPreview = filePreview.filePath !== null;

  const activeWorkspaceHasRepo = !!workspaces.find(
    (w) => w.id === sidebar.activeWorkspaceId
  )?.repo_url;

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
        onSelectWorkspace={handleSelectWorkspace}
        workspaceTree={sidebarWorkspaceTree}
        treeWorkspaceId={treeWorkspaceId}
        onWorkspaceTreeUpdate={handleSidebarTreeUpdate}
        activeFilePath={filePreview.filePath}
        onFileClick={filePreview.openFile}
        onFileDeleted={filePreview.handleFileDeleted}
        onFileRenamed={filePreview.handleFileRenamed}
        activeWorkspaceHasRepo={activeWorkspaceHasRepo}
        onNewWorkspace={handleNewWorkspace}
        onDeleteWorkspace={handleDeleteWorkspace}
        onClearFilter={() => {
          sidebar.setActiveWorkspace(null);
          setSidebarWorkspaceTree(null);
          setTreeWorkspaceId(null);
          filePreview.closePreview();
        }}
        workspaces={workspaces}
        workspacesLoading={workspacesLoading}
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
                fileIndex={fileIndex}
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
              workspaceFiles={Array.from(fileIndex.values())}
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
        onCreated={handleWorkspaceCreated}
      />
    </div>
  );
}
