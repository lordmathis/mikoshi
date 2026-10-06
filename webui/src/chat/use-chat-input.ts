import { useState, useRef, useCallback, useEffect } from "react";
import type { Message, FileResource } from "../lib/api.ts";
import { localCache } from "../lib/local-cache.ts";

const DRAFT_WRITE_DELAY_MS = 300;

function draftKey(chatId: string): string {
  return `mikoshi-draft:${chatId}`;
}

function isCoarsePointer(): boolean {
  return window.matchMedia("(pointer: coarse)").matches;
}

interface UseChatInputOptions {
  chatId?: string;
  onSend: (text: string, files: FileResource[]) => Promise<void>;
  onEdit: (text: string) => Promise<void>;
  messages: Message[];
  getFiles: () => FileResource[];
  isSending: boolean;
  onSendComplete?: () => void;
  onEditComplete?: () => void;
}

interface UseChatInputReturn {
  inputValue: string;
  setInputValue: (value: string) => void;
  isEditingMode: boolean;
  handleSend: () => Promise<void>;
  handleEdit: () => void;
  cancelEdit: () => void;
  handleKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function useChatInput({
  chatId,
  onSend,
  onEdit,
  messages,
  getFiles,
  isSending,
  onSendComplete,
  onEditComplete,
}: UseChatInputOptions): UseChatInputReturn {
  const [inputValue, setInputValue] = useState(() =>
    chatId ? localCache.get<string>(draftKey(chatId)) ?? "" : ""
  );
  const [isEditingMode, setIsEditingMode] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const chatIdRef = useRef(chatId);
  chatIdRef.current = chatId;
  const draftLoadedForRef = useRef<string | undefined>(chatId);

  useEffect(() => {
    if (draftLoadedForRef.current === chatId) return;
    draftLoadedForRef.current = chatId;
    setInputValue(chatId ? localCache.get<string>(draftKey(chatId)) ?? "" : "");
  }, [chatId]);

  useEffect(() => {
    if (!chatId) return;
    const scheduledFor = chatId;
    const value = inputValue;
    const timer = setTimeout(() => {
      if (chatIdRef.current !== scheduledFor) return;
      localCache.set(draftKey(scheduledFor), value);
    }, DRAFT_WRITE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [inputValue, chatId]);

  const clearDraft = useCallback(() => {
    if (chatIdRef.current) localCache.remove(draftKey(chatIdRef.current));
  }, []);

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || isSending) return;

    const text = inputValue.trim();
    const files = getFiles();

    setInputValue("");
    clearDraft();

    if (isEditingMode) {
      await onEdit(text);
      setIsEditingMode(false);
      onEditComplete?.();
    } else {
      await onSend(text, files);
      onSendComplete?.();
    }
  }, [inputValue, isSending, getFiles, isEditingMode, onSend, onEdit, onSendComplete, onEditComplete, clearDraft]);

  const handleEdit = useCallback(() => {
    const lastUserMessage = [...messagesRef.current].reverse().find((msg) => msg.role === "user");

    if (!lastUserMessage) return;

    setInputValue(lastUserMessage.content);
    setIsEditingMode(true);
    textareaRef.current?.focus();
  }, []);

  const cancelEdit = useCallback(() => {
    setInputValue("");
    setIsEditingMode(false);
    clearDraft();
  }, [clearDraft]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== "Enter" || e.shiftKey) return;
    // Touch devices: Enter inserts a newline, sending happens via the button.
    if (isCoarsePointer()) return;
    e.preventDefault();
    void handleSend();
  }, [handleSend]);

  return {
    inputValue,
    setInputValue,
    isEditingMode,
    handleSend,
    handleEdit,
    cancelEdit,
    handleKeyDown,
    textareaRef,
  };
}