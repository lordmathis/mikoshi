import { useState, useCallback } from "react";

export interface UseMentionTriggerOptions<T> {
  trigger: string;
  items: T[];
  searchFn: (item: T, query: string) => boolean;
}

export interface UseMentionTriggerReturn<T> {
  show: boolean;
  filteredItems: T[];
  selectedIndex: number;
  query: string;
  triggerStart: number;
  handleInputChange: (value: string, cursorPos: number) => void;
  handleKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => boolean;
  insert: (item: T, getInsertText: (item: T) => string) => { text: string; cursorPos: number };
  close: () => void;
  setSelectedIndex: (index: number) => void;
}

export function useMentionTrigger<T>({
  trigger,
  items,
  searchFn,
}: UseMentionTriggerOptions<T>): UseMentionTriggerReturn<T> {
  const [show, setShow] = useState(false);
  const [query, setQuery] = useState("");
  const [triggerStart, setTriggerStart] = useState(-1);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filteredItems = items.filter((item) => searchFn(item, query));

  const close = useCallback(() => {
    setShow(false);
    setQuery("");
    setTriggerStart(-1);
    setSelectedIndex(0);
  }, []);

  const handleInputChange = useCallback(
    (value: string, cursorPos: number) => {
      const textBeforeCursor = value.substring(0, cursorPos);
      const lastIndex = textBeforeCursor.lastIndexOf(trigger);

      if (lastIndex !== -1) {
        const textAfterTrigger = textBeforeCursor.substring(lastIndex + trigger.length);
        if (!textAfterTrigger.includes(" ") && !textAfterTrigger.includes("\n")) {
          const charBefore = lastIndex > 0 ? value[lastIndex - 1] : " ";
          if (charBefore === " " || charBefore === "\n" || lastIndex === 0) {
            setShow(true);
            setQuery(textAfterTrigger);
            setTriggerStart(lastIndex);
            setSelectedIndex(0);
            return;
          }
        }
      }

      setShow(false);
    },
    [trigger]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>): boolean => {
      if (!show || filteredItems.length === 0) return false;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, filteredItems.length - 1));
        return true;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        return true;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        return true;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        return true;
      }

      return false;
    },
    [show, filteredItems.length, close]
  );

  const insert = useCallback(
    (item: T, getInsertText: (item: T) => string) => {
      if (triggerStart === -1) return { text: "", cursorPos: 0 };

      const textarea = document.querySelector<HTMLTextAreaElement>(".typing-area");
      const currentValue = textarea?.value ?? "";
      const insertText = getInsertText(item);

      const before = currentValue.substring(0, triggerStart);
      const after = currentValue.substring(triggerStart + trigger.length + query.length);
      const newText = `${before}${insertText}${after}`;
      const newCursorPos = triggerStart + insertText.length;

      close();
      return { text: newText, cursorPos: newCursorPos };
    },
    [triggerStart, trigger, query, close]
  );

  return {
    show,
    filteredItems,
    selectedIndex,
    query,
    triggerStart,
    handleInputChange,
    handleKeyDown,
    insert,
    close,
    setSelectedIndex,
  };
}
