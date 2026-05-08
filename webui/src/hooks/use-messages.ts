import { useState, useEffect, useCallback } from "react";
import { api, type Message, type FileResource, type WorkspaceUpdateData } from "../lib/api";
import { type ChatSettings } from "../components/chat-settings-dialog";

export function useMessages(
  chatId: string | undefined,
  onWorkspaceUpdate?: (data: WorkspaceUpdateData) => void
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [chatSettings, setChatSettings] = useState<ChatSettings>({
    baseModel: "",
    systemPrompt: "",
    enabledTools: [],
    modelParams: {
      max_iterations: 5,
    },
  });

  const loadDefaultSettings = useCallback(async () => {
    try {
      const defaults = await api.getDefaultChatConfig();
      setChatSettings({
        baseModel: defaults.model || "",
        systemPrompt: defaults.system_prompt || "",
        enabledTools: defaults.tool_servers || [],
        modelParams: defaults.model_params || { max_iterations: 5 },
      });
    } catch (error) {
      console.error("Failed to load default settings:", error);
    }
  }, []);

  const reloadMessages = useCallback(async () => {
    if (!chatId) return;
    try {
      const chatData = await api.getChat(chatId);
      setMessages(chatData.messages);
      setChatSettings({
        baseModel: chatData.model || "",
        systemPrompt: chatData.system_prompt || "",
        enabledTools: chatData.tool_servers || [],
        modelParams: chatData.model_params || {
          max_iterations: 5,
        },
      });
    } catch (error) {
      console.error("Failed to reload messages:", error);
    }
  }, [chatId]);

  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      loadDefaultSettings();
      return;
    }
    const fetchInitial = async () => {
      setIsLoading(true);
      await reloadMessages();
      setIsLoading(false);
    };
    fetchInitial();
  }, [chatId, reloadMessages, loadDefaultSettings]);

  const send = async (text: string, files: FileResource[]) => {
    if (!chatId) return;
    
    const tempId = `temp-${Date.now()}`;
    const optimisticMessage: Message = {
      id: tempId,
      role: 'user',
      content: text,
      sequence: messages.length,
      created_at: new Date().toISOString(),
      files: files.map(f => ({
        id: f.id,
        filename: f.filename,
        content_type: f.content_type,
        source: f.source,
      })),
    };
    
    setMessages(prev => [...prev, optimisticMessage]);
    
    try {
      setIsSending(true);
      for await (const event of api.streamMessage(chatId, {
        message: text,
        file_ids: files.map(f => f.id),
      })) {
        if (event.type === 'message') {
          setMessages(prev => [...prev, event.data as Message]);
        } else if (event.type === 'workspace_update') {
          onWorkspaceUpdate?.(event.data as WorkspaceUpdateData);
        } else if (event.type === 'error') {
          setMessages(prev => prev.filter(m => m.id !== tempId));
          throw new Error((event.data as { message: string }).message);
        }
      }
    } catch (error) {
      setMessages(prev => prev.filter(m => m.id !== tempId));
      throw error;
    } finally {
      setIsSending(false);
    }
  };

  const retry = async () => {
    if (!chatId) return;
    try {
      setIsSending(true);
      await reloadMessages();
      for await (const event of api.streamRetry(chatId)) {
        if (event.type === 'message') {
          setMessages(prev => [...prev, event.data as Message]);
        } else if (event.type === 'workspace_update') {
          onWorkspaceUpdate?.(event.data as WorkspaceUpdateData);
        } else if (event.type === 'error') {
          throw new Error((event.data as { message: string }).message);
        }
      }
    } finally {
      setIsSending(false);
    }
  };

  const edit = async (text: string) => {
    if (!chatId) return;
    try {
      setIsSending(true);
      await reloadMessages();
      for await (const event of api.streamEdit(chatId, text)) {
        if (event.type === 'message') {
          setMessages(prev => [...prev, event.data as Message]);
        } else if (event.type === 'workspace_update') {
          onWorkspaceUpdate?.(event.data as WorkspaceUpdateData);
        } else if (event.type === 'error') {
          throw new Error((event.data as { message: string }).message);
        }
      }
    } finally {
      setIsSending(false);
    }
  };

  return {
    messages,
    isLoading,
    isSending,
    chatSettings,
    setChatSettings,
    send,
    retry,
    edit,
  };
}
