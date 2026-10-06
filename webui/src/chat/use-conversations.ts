import { useState, useEffect, useCallback, useRef } from "react";
import { api, type Chat, type ChatConfig } from "../lib/api.ts";
import { type Conversation } from "../sidebar/sidebar.tsx";
import { formatTimestamp } from "../lib/formatters.ts";

const PAGE_SIZE = 20;

function toConversation(chat: Chat): Conversation {
  return {
    id: chat.id,
    title: chat.title,
    timestamp: formatTimestamp(chat.updated_at),
    updated_at: chat.updated_at,
    preview: chat.model || undefined,
    workspace_id: chat.workspace_id ?? null,
  };
}

export function useConversations(activeWorkspaceId: string | null) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const workspaceRef = useRef(activeWorkspaceId);
  workspaceRef.current = activeWorkspaceId;
  const conversationsRef = useRef(conversations);
  conversationsRef.current = conversations;

  const mergePage = useCallback((incoming: Chat[]) => {
    setConversations((prev) => {
      const byId = new Map(prev.map((c) => [c.id, c]));
      for (const chat of incoming) {
        byId.set(chat.id, toConversation(chat));
      }
      // Page shifts from chats moving in updated_at order are absorbed by
      // the dedupe above; re-sorting keeps the merged list consistent.
      return [...byId.values()].sort((a, b) =>
        b.updated_at.localeCompare(a.updated_at)
      );
    });
  }, []);

  const fetchPage = useCallback(async (offset: number) => {
    const requestWorkspace = workspaceRef.current;
    try {
      setIsLoading(true);
      const response = await api.listChats(PAGE_SIZE, offset, requestWorkspace);
      if (workspaceRef.current !== requestWorkspace) return;
      mergePage(response.chats);
      setHasMore(response.chats.length === PAGE_SIZE);
    } catch (error) {
      console.error("Failed to fetch conversations:", error);
    } finally {
      if (workspaceRef.current === requestWorkspace) setIsLoading(false);
    }
  }, [mergePage]);

  useEffect(() => {
    setConversations([]);
    setHasMore(false);
    void fetchPage(0);
  }, [activeWorkspaceId, fetchPage]);

  const refresh = useCallback(() => fetchPage(0), [fetchPage]);

  const loadMore = useCallback(() => {
    void fetchPage(conversationsRef.current.length);
  }, [fetchPage]);

  const upsertConversation = useCallback((chat: Chat) => {
    setConversations((prev) => {
      if (prev.some((c) => c.id === chat.id)) return prev;
      // Prepend: the opened chat is what the user is looking at.
      return [toConversation(chat), ...prev];
    });
  }, []);

  const createConversation = useCallback(async (
    overrideConfig?: Partial<ChatConfig>,
    workspaceId?: string | null
  ) => {
    const defaults = await api.getDefaultChatConfig(workspaceId);
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
  }, [refresh]);

  const deleteConversation = useCallback(async (id: string) => {
    await api.deleteChat(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
  }, []);

  const branchConversation = useCallback(async (id: string, messageId: string) => {
    const currentChat = conversationsRef.current.find((c) => c.id === id);
    const branchTitle = currentChat ? `${currentChat.title} (branch)` : undefined;
    const branchedChat = await api.branchChat(id, messageId, branchTitle);
    await refresh();
    return branchedChat.id;
  }, [refresh]);

  return {
    conversations,
    isLoading,
    hasMore,
    loadMore,
    refresh,
    createConversation,
    deleteConversation,
    branchConversation,
    upsertConversation,
  };
}
