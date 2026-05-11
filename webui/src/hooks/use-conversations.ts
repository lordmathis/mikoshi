import { useState, useEffect, useCallback } from "react";
import { api, type ChatConfig } from "../lib/api";
import { type Conversation } from "../components/sidebar";
import { formatTimestamp } from "../lib/formatters";

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await api.listChats(20);
      const formattedChats: Conversation[] = response.chats.map((chat) => ({
        id: chat.id,
        title: chat.title,
        timestamp: formatTimestamp(chat.updated_at),
        preview: chat.model || undefined,
        workspace_id: chat.workspace_id ?? null,
      }));
      setConversations(formattedChats);
    } catch (error) {
      console.error("Failed to refresh conversations:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createConversation = async (
    overrideConfig?: Partial<ChatConfig>,
    workspaceId?: string | null
  ) => {
    const defaults = await api.getDefaultChatConfig();
    const model = overrideConfig?.model ?? defaults.model;
    if (!model) throw new Error("No model available — configure a default in settings.");
 
    const config: ChatConfig = {
      model,
      system_prompt: overrideConfig?.system_prompt ?? defaults.system_prompt ?? undefined,
      tool_servers: overrideConfig?.tool_servers ?? defaults.tool_servers ?? [],
      model_params: overrideConfig?.model_params ?? defaults.model_params ?? undefined,
    };
 
    const chat = await api.createChat({
      title: "Untitled Chat",
      config,
      workspace_id: workspaceId,
    });
    await refresh();
    return chat.id;
  };

  const deleteConversation = async (id: string) => {
    await api.deleteChat(id);
    await refresh();
  };

  const branchConversation = async (id: string, messageId: string) => {
    const currentChat = conversations.find((c) => c.id === id);
    const branchTitle = currentChat ? `${currentChat.title} (branch)` : undefined;
    const branchedChat = await api.branchChat(id, messageId, branchTitle);
    await refresh();
    return branchedChat.id;
  };

  return {
    conversations,
    isLoading,
    createConversation,
    deleteConversation,
    branchConversation,
    refresh,
  };
}
