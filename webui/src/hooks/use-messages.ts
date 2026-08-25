import { useState, useEffect, useCallback, useRef } from "react";
import { api, type Message, type FileResource, type PendingApproval } from "../lib/api";
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

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

export function useMessages(
  chatId: string | undefined,
  onWorkspaceChange?: (paths: string[]) => void
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Record<string, PendingApproval>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadedChatId, setLoadedChatId] = useState<string | undefined>(undefined);
  const streamAbortRef = useRef<AbortController | null>(null);
  const pendingApprovalsRef = useRef<Record<string, PendingApproval>>({});
  pendingApprovalsRef.current = pendingApprovals;
  const chatIdRef = useRef(chatId);
  chatIdRef.current = chatId;
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
      if (chatIdRef.current !== chatId) return;
      setMessages(chatData.messages);
      setChatSettings({
        baseModel: chatData.model || "",
        systemPrompt: chatData.system_prompt || "",
        enabledTools: chatData.tool_servers || [],
        modelParams: chatData.model_params || {
          max_iterations: 5,
        },
      });
      const { approvals } = await api.listApprovals(chatId);
      if (chatIdRef.current !== chatId) return;
      const map: Record<string, PendingApproval> = {};
      for (const a of approvals) {
        if (a.message_id) map[a.message_id] = a;
      }
      setPendingApprovals(map);
      setLoadError(null);
    } catch (error) {
      console.error("Failed to reload messages:", error);
      if (chatIdRef.current !== chatId) return;
      setMessages([]);
      setPendingApprovals({});
      setLoadError(error instanceof Error ? error.message : "Failed to load messages");
    } finally {
      if (chatIdRef.current === chatId) {
        setLoadedChatId(chatId);
      }
    }
  }, [chatId]);

  const beginStream = useCallback(() => {
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    return controller;
  }, []);

  const handleEvent = useCallback(
    (event: { type: string; data: unknown }) => {
      if (event.type === "message") {
        const msg = event.data as Message;
        setMessages((prev) => {
          const idx = prev.findIndex((m) => m.id === msg.id);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = msg;
            return next;
          }
          return [...prev, msg];
        });

        if (msg.role === "tool") {
          const change = tryParseWorkspaceChange(msg.content);
          if (change) {
            onWorkspaceChange?.(change.paths);
          }
        }
      } else if (event.type === "tool_approval_request") {
        const req = event.data as {
          approval_id: string;
          message_id: string;
          tool_name: string;
          arguments: Record<string, unknown>;
        };
        const approval: PendingApproval = {
          id: req.approval_id,
          message_id: req.message_id,
          tool_name: req.tool_name,
          arguments: req.arguments,
          created_at: null,
        };
        setPendingApprovals((prev) => ({ ...prev, [req.message_id]: approval }));
      } else if (event.type === "error") {
        const errMsg = (event.data as { message: string }).message;
        console.error('[Messages] error event:', errMsg);
        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: "error",
            content: errMsg,
            sequence: prev.length,
            created_at: new Date().toISOString(),
          } as Message,
        ]);
      }
    },
    [onWorkspaceChange]
  );

  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      setPendingApprovals({});
      setLoadError(null);
      setLoadedChatId(undefined);
      loadDefaultSettings();
      return;
    }
    const abortController = beginStream();
    const fetchInitial = async () => {
      setIsLoading(true);
      await reloadMessages();
      setIsLoading(false);
      if (chatIdRef.current !== chatId || abortController.signal.aborted) return;
      const { active } = await api.getStreamStatus(chatId);
      if (chatIdRef.current !== chatId || abortController.signal.aborted) return;
      if (!active) return;
      setIsSending(true);
      try {
        for await (const event of api.subscribeStream(chatId, abortController.signal)) {
          handleEvent(event);
        }
      } catch (e) {
        if (isAbortError(e)) return;
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
  }, [chatId, reloadMessages, loadDefaultSettings, handleEvent, beginStream]);

  const send = useCallback(async (text: string, files: FileResource[]) => {
    if (!chatId) return;

    const controller = beginStream();

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
      }, controller.signal)) {
        if (chatIdRef.current !== chatId) return;
        handleEvent(event);
      }
      console.debug('[Messages] send() COMPLETE — stream ended normally');
    } catch (error) {
      if (isAbortError(error) || chatIdRef.current !== chatId) return;
      console.error('[Messages] send() ERROR:', error);
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
      throw error;
    } finally {
      console.debug('[Messages] send() finally — setting isSending=false');
      setIsSending(false);
      if (streamAbortRef.current === controller) {
        streamAbortRef.current = null;
      }
    }
  }, [chatId, messages.length, beginStream, handleEvent]);

  const retry = useCallback(async () => {
    if (!chatId) return;
    const controller = beginStream();
    try {
      setIsSending(true);
      await reloadMessages();
      for await (const event of api.streamRetry(chatId, controller.signal)) {
        if (chatIdRef.current !== chatId) return;
        handleEvent(event);
      }
    } catch (error) {
      if (!isAbortError(error) && chatIdRef.current === chatId) throw error;
    } finally {
      setIsSending(false);
      if (streamAbortRef.current === controller) {
        streamAbortRef.current = null;
      }
    }
  }, [chatId, beginStream, reloadMessages, handleEvent]);

  const edit = useCallback(async (text: string) => {
    if (!chatId) return;
    const controller = beginStream();
    try {
      setIsSending(true);
      await reloadMessages();
      for await (const event of api.streamEdit(chatId, text, controller.signal)) {
        if (chatIdRef.current !== chatId) return;
        handleEvent(event);
      }
    } catch (error) {
      if (!isAbortError(error) && chatIdRef.current === chatId) throw error;
    } finally {
      setIsSending(false);
      if (streamAbortRef.current === controller) {
        streamAbortRef.current = null;
      }
    }
  }, [chatId, beginStream, reloadMessages, handleEvent]);

  const resolveApproval = useCallback(
    (messageId: string, content: string) => {
      setPendingApprovals((prev) => {
        const next = { ...prev };
        delete next[messageId];
        return next;
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, content, status: "completed" }
            : m
        )
      );
    },
    []
  );

  const approveApproval = useCallback(
    async (messageId: string, scope: "once" | "always") => {
      const approval = pendingApprovalsRef.current[messageId];
      if (!approval) return;
      try {
        const { result } = await api.approveTool(approval.id, scope);
        resolveApproval(messageId, result);
      } catch (e) {
        console.error("[Messages] approve failed:", e);
      }
    },
    [resolveApproval]
  );

  const denyApproval = useCallback(
    async (messageId: string) => {
      const approval = pendingApprovalsRef.current[messageId];
      if (!approval) return;
      try {
        await api.denyTool(approval.id);
        resolveApproval(
          messageId,
          `Tool '${approval.tool_name}' was denied by the user.`
        );
      } catch (e) {
        console.error("[Messages] deny failed:", e);
      }
    },
    [resolveApproval]
  );

  const isStale = loadedChatId !== chatId;

  return {
    messages: isStale ? [] : messages,
    isLoading: isLoading || isStale,
    isSending,
    loadError: isStale ? null : loadError,
    chatSettings,
    setChatSettings,
    pendingApprovals: isStale ? {} : pendingApprovals,
    send,
    retry,
    edit,
    approveApproval,
    denyApproval,
  };
}
