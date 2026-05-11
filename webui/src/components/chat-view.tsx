import { useState, useEffect, useRef, useCallback } from "react";
import { SidebarSegmentedControl } from "./sidebar-segmented";
import { CreateNodeDialog } from "./create-node-dialog";
import { AddConnectorDialog } from "./add-connector-dialog";
import { ChatHeader } from "./chat-header";
import { MessagesList } from "./messages-list";
import { ChatInput } from "./chat-input";
import { FilePreview } from "./file-preview";
import { useConversations } from "../hooks/use-conversations";
import { useMessages } from "../hooks/use-messages";
import { useChatFiles } from "../hooks/use-chat-files";
import { useChatInput } from "../hooks/use-chat-input";
import { useSidebar } from "../hooks/use-sidebar";
import { api, type ConnectorEntry, type FileNode, type WorkspaceUpdateData } from "../lib/api";

export function ChatView() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isConnectorDialogOpen, setIsConnectorDialogOpen] = useState(false);
  const [editingConnectorEntry, setEditingConnectorEntry] = useState<ConnectorEntry | null>(null);
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>();
  const [isCreateNodeOpen, setIsCreateNodeOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<{ id: string; name: string }[]>([]);
  const [workspaceRefreshTrigger, setWorkspaceRefreshTrigger] = useState(0);
  const [sidebarWorkspaceTree, setSidebarWorkspaceTree] = useState<FileNode | null>(null);
  const [previewFilePath, setPreviewFilePath] = useState<string | null>(null);
  const [previewFileContent, setPreviewFileContent] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [fileIndex, setFileIndex] = useState<Map<string, string>>(new Map());

  const conversations = useConversations();
  const sidebar = useSidebar();

  const handleWorkspaceSSEEvent = useCallback(
    (data: WorkspaceUpdateData) => {
      setSidebarWorkspaceTree(data.tree);
    },
    []
  );

  const messages = useMessages(currentConversationId, handleWorkspaceSSEEvent);
  const files = useChatFiles(currentConversationId);

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
    api.listWorkspaces().then((res) => {
      setWorkspaces(res.workspaces.map((w) => ({ id: w.id, name: w.name })));
    }).catch(() => {});
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

  const handleRetry = async () => {
    await messages.retry();
    conversations.refresh();
  };

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
    }
    conversations.refresh();
  };

  const handleWorkspaceCreated = (ws: { id: string; name: string }) => {
    setWorkspaceRefreshTrigger((n) => n + 1);
    sidebar.setActiveWorkspace(ws.id);
    sidebar.setActiveTab("data");
  };

  const handleFileClick = async (path: string) => {
    const wsId = sidebar.activeWorkspaceId;
    if (!wsId) return;
    setPreviewFilePath(path);
    setPreviewFileContent(null);
    setPreviewLoading(true);
    try {
      const content = await api.getWorkspaceFile(wsId, path);
      setPreviewFileContent(content);
    } catch (error) {
      console.error("Failed to fetch workspace file:", error);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleClosePreview = () => {
    setPreviewFilePath(null);
    setPreviewFileContent(null);
  };

  const handleSidebarTreeUpdate = useCallback((tree: FileNode) => {
    setSidebarWorkspaceTree(tree);
  }, []);

  const showPreview = previewFilePath !== null;

  return (
    <div className="relative flex h-screen" style={{ background: "#0a0a0c" }}>
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
        onSelectWorkspace={sidebar.setActiveWorkspace}
        workspaceTree={sidebarWorkspaceTree}
        onWorkspaceTreeUpdate={handleSidebarTreeUpdate}
        activeFilePath={previewFilePath}
        onFileClick={handleFileClick}
        onNewWorkspace={handleNewWorkspace}
        onDeleteWorkspace={handleDeleteWorkspace}
        onClearFilter={() => {
          sidebar.setActiveWorkspace(null);
          setSidebarWorkspaceTree(null);
          handleClosePreview();
        }}
        workspaces={workspaces}
        workspaceRefreshTrigger={workspaceRefreshTrigger}
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
              <FilePreview
                filePath={previewFilePath}
                fileContent={previewFileContent}
                isLoading={previewLoading}
                onClose={handleClosePreview}
                workspaceId={sidebar.activeWorkspaceId}
                fileIndex={fileIndex}
                onFileClick={handleFileClick}
              />
            </div>
          )}

          <div className="flex flex-col flex-1 min-w-0">
            <MessagesList
              messages={messages.messages}
              isLoading={messages.isLoading}
              isSending={messages.isSending}
              currentConversationId={currentConversationId}
              messagesEndRef={messagesEndRef}
              onBranch={async (messageId) => {
                const id = await conversations.branchConversation(currentConversationId!, messageId);
                setCurrentConversationId(id);
              }}
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
                  setEditingConnectorEntry(entry);
                  setIsConnectorDialogOpen(true);
                }
              }}
              onFileUploadClick={handleFileUploadClick}
              onConnectorDialogOpen={() => {
                setEditingConnectorEntry(null);
                setIsConnectorDialogOpen(true);
              }}
              onChatUpdated={conversations.refresh}
              textareaRef={chatInput.textareaRef}
              fileInputRef={fileInputRef}
              onFileChange={(e) => {
                if (e.target.files) files.uploadFiles(Array.from(e.target.files));
              }}
            />
          </div>
        </div>
      </div>

      <AddConnectorDialog
        open={isConnectorDialogOpen}
        onOpenChange={(open) => {
          setIsConnectorDialogOpen(open);
          if (!open) setEditingConnectorEntry(null);
        }}
        chatId={currentConversationId}
        editingEntry={editingConnectorEntry ?? undefined}
        onFilesAdded={(entry) => {
          if (editingConnectorEntry) {
            files.updateConnectorEntry(
              editingConnectorEntry.connectorId,
              editingConnectorEntry.resourceId,
              entry
            );
          } else {
            files.addConnectorEntry(entry);
          }
          setEditingConnectorEntry(null);
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
