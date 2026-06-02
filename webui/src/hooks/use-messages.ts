import { useState, useEffect, useCallback, useRef } from "react";
import { api, type Message, type FileResource } from "../lib/api";
import { type ChatSettings } from "../components/chat-settings-dialog";

function tryParseWorkspaceChange(
  content: string,
): { paths: string[] } | null {
  try {
    const parsed = JSON.parse(content);
    if (parsed && parsed.__workspace === true) {
      return { paths: parsed.paths ?? [] };
    }
  } catch {}
  return null;
}

export function useMessages(
  chatId: string | undefined,
  onWorkspaceChange?: (paths: string[]) => void
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const pollStreamStatus = useCallback(async () => {
    if (!chatId) return;
    try {
      const { active } = await api.getStreamStatus(chatId);
      if (active) {
        setIsSending(true);
        await reloadMessages();
        pollingRef.current = setTimeout(pollStreamStatus, 2000);
      } else {
        await reloadMessages();
        setIsSending(false);
        pollingRef.current = null;
      }
    } catch {
      pollingRef.current = setTimeout(pollStreamStatus, 3000);
    }
  }, [chatId, reloadMessages]);

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
      const { active } = await api.getStreamStatus(chatId);
      if (active) {
        setIsSending(true);
        pollingRef.current = setTimeout(pollStreamStatus, 2000);
      }
    };
    fetchInitial();
    return () => stopPolling();
  }, [chatId, reloadMessages, loadDefaultSettings, pollStreamStatus, stopPolling]);

  useEffect(() => {
    if (!chatId) return;
    const handleVisibility = () => {
      if (document.visibilityState === "visible" && pollingRef.current === null) {
        pollStreamStatus();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [chatId, pollStreamStatus]);

  const handleEvent = useCallback(
    (event: { type: string; data: unknown }) => {
      if (event.type === "message") {
        const msg = event.data as Message;
        console.debug('[Messages] received:', msg.role, msg.id, msg.content?.slice(0, 80));
        setMessages((prev) => [...prev, msg]);

        if (msg.role === "tool") {
          const change = tryParseWorkspaceChange(msg.content);
          if (change) {
            onWorkspaceChange?.(change.paths);
          }
        }
      } else if (event.type === "error") {
        const errMsg = (event.data as { message: string }).message;
        console.error('[Messages] error event:', errMsg);
        throw new Error(errMsg);
      }
    },
    [onWorkspaceChange]
  );

  const send = async (text: string, files: FileResource[]) => {
    if (!chatId) return;

    const tempId = `temp-${Date.now()}`;
    const optimisticMessage: Message = {
      id: tempId,
      role: "user",
      content: text,
      sequence: messages.length,
      created_at: new Date().toISOString(),
      files: files.map((f) => ({
        id: f.id,
        filename: f.filename,
        content_type: f.content_type,
        source: f.source,
      })),
    };

    setMessages((prev) => [...prev, optimisticMessage]);

    console.debug('[Messages] send() START — streaming message to chat', chatId);
    try {
      setIsSending(true);
      for await (const event of api.streamMessage(chatId, {
        message: text,
        file_ids: files.map((f) => f.id),
      })) {
        handleEvent(event);
      }
      console.debug('[Messages] send() COMPLETE — stream ended normally');
    } catch (error) {
      console.error('[Messages] send() ERROR:', error);
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
      throw error;
    } finally {
      console.debug('[Messages] send() finally — setting isSending=false');
      setIsSending(false);
    }
  };

  const retry = async () => {
    if (!chatId) return;
    try {
      setIsSending(true);
      await reloadMessages();
      for await (const event of api.streamRetry(chatId)) {
        handleEvent(event);
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
        handleEvent(event);
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
