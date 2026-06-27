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
  const [loadedChatId, setLoadedChatId] = useState<string | undefined>(undefined);
  const streamAbortRef = useRef<AbortController | null>(null);
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
      setLoadedChatId(chatId);
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

  const abortActiveStream = useCallback(() => {
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
  }, []);

  const handleEvent = useCallback(
    (event: { type: string; data: unknown }) => {
      if (event.type === "message") {
        const msg = event.data as Message;
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

  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      setLoadedChatId(undefined);
      loadDefaultSettings();
      return;
    }
    const abortController = new AbortController();
    streamAbortRef.current = abortController;
    const fetchInitial = async () => {
      setIsLoading(true);
      await reloadMessages();
      setIsLoading(false);
      const { active } = await api.getStreamStatus(chatId);
      if (!active) return;
      setIsSending(true);
      try {
        for await (const event of api.subscribeStream(chatId, abortController.signal)) {
          handleEvent(event);
        }
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        console.error("[Messages] stream reconnect error:", e);
      } finally {
        setIsSending(false);
        if (streamAbortRef.current === abortController) {
          streamAbortRef.current = null;
        }
      }
    };
    fetchInitial();
    return () => abortController.abort();
  }, [chatId, reloadMessages, loadDefaultSettings, handleEvent]);

  const send = useCallback(async (text: string, files: FileResource[]) => {
    if (!chatId) return;

    abortActiveStream();

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
  }, [chatId, messages.length, abortActiveStream, handleEvent]);

  const retry = useCallback(async () => {
    if (!chatId) return;
    abortActiveStream();
    try {
      setIsSending(true);
      await reloadMessages();
      for await (const event of api.streamRetry(chatId)) {
        handleEvent(event);
      }
    } finally {
      setIsSending(false);
    }
  }, [chatId, abortActiveStream, reloadMessages, handleEvent]);

  const edit = useCallback(async (text: string) => {
    if (!chatId) return;
    abortActiveStream();
    try {
      setIsSending(true);
      await reloadMessages();
      for await (const event of api.streamEdit(chatId, text)) {
        handleEvent(event);
      }
    } finally {
      setIsSending(false);
    }
  }, [chatId, abortActiveStream, reloadMessages, handleEvent]);

  const isStale = loadedChatId !== chatId;

  return {
    messages: isStale ? [] : messages,
    isLoading: isLoading || isStale,
    isSending,
    chatSettings,
    setChatSettings,
    send,
    retry,
    edit,
  };
}
