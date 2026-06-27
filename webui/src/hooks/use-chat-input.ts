import { useState, useRef, useCallback } from "react";
import type { Message, FileResource } from "../lib/api";

interface UseChatInputOptions {
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
  onSend,
  onEdit,
  messages,
  getFiles,
  isSending,
  onSendComplete,
  onEditComplete,
}: UseChatInputOptions): UseChatInputReturn {
  const [inputValue, setInputValue] = useState("");
  const [isEditingMode, setIsEditingMode] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || isSending) return;

    const text = inputValue.trim();
    const files = getFiles();

    setInputValue("");

    if (isEditingMode) {
      await onEdit(text);
      setIsEditingMode(false);
      onEditComplete?.();
    } else {
      await onSend(text, files);
      onSendComplete?.();
    }
  }, [inputValue, isSending, getFiles, isEditingMode, onSend, onEdit, onSendComplete, onEditComplete]);

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
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
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