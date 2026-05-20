import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChatInput } from "../use-chat-input";
import type { Message, FileResource } from "../../lib/api";

const noop = () => Promise.resolve();
const noFiles: FileResource[] = [];
const emptyMessages: Message[] = [];

function renderChatInput(overrides: Partial<Parameters<typeof useChatInput>[0]> = {}) {
  return renderHook(() =>
    useChatInput({
      onSend: vi.fn().mockResolvedValue(undefined),
      onEdit: vi.fn().mockResolvedValue(undefined),
      messages: emptyMessages,
      getFiles: () => noFiles,
      isSending: false,
      ...overrides,
    })
  );
}

describe("useChatInput", () => {
  it("sends message and clears input", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const { result } = renderChatInput({ onSend });

    act(() => result.current.setInputValue("hello"));
    await act(() => result.current.handleSend());

    expect(onSend).toHaveBeenCalledWith("hello", noFiles);
    expect(result.current.inputValue).toBe("");
  });

  it("does nothing on empty input", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const { result } = renderChatInput({ onSend });

    await act(() => result.current.handleSend());

    expect(onSend).not.toHaveBeenCalled();
  });

  it("does nothing when isSending is true", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const { result } = renderChatInput({ onSend, isSending: true });

    act(() => result.current.setInputValue("hello"));
    await act(() => result.current.handleSend());

    expect(onSend).not.toHaveBeenCalled();
  });

  it("calls onEdit (not onSend) when in edit mode", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const onEdit = vi.fn().mockResolvedValue(undefined);
    const messages: Message[] = [
      { id: "1", role: "user", content: "original message", sequence: 0, created_at: "" },
    ];
    const { result } = renderChatInput({ onSend, onEdit, messages });

    act(() => result.current.handleEdit());
    expect(result.current.inputValue).toBe("original message");
    expect(result.current.isEditingMode).toBe(true);

    await act(() => result.current.handleSend());

    expect(onEdit).toHaveBeenCalledWith("original message");
    expect(onSend).not.toHaveBeenCalled();
    expect(result.current.isEditingMode).toBe(false);
  });

  it("cancelEdit resets input and editing mode", () => {
    const messages: Message[] = [
      { id: "1", role: "user", content: "original", sequence: 0, created_at: "" },
    ];
    const { result } = renderChatInput({ messages });

    act(() => result.current.handleEdit());
    expect(result.current.isEditingMode).toBe(true);

    act(() => result.current.cancelEdit());
    expect(result.current.inputValue).toBe("");
    expect(result.current.isEditingMode).toBe(false);
  });

  it("Enter without Shift triggers send", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const { result } = renderChatInput({ onSend });

    act(() => result.current.setInputValue("hello"));
    act(() =>
      result.current.handleKeyDown({
        key: "Enter",
        shiftKey: false,
        preventDefault: vi.fn(),
      } as any)
    );
    await act(() => Promise.resolve());

    expect(onSend).toHaveBeenCalled();
  });

  it("Enter with Shift does NOT trigger send", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const { result } = renderChatInput({ onSend });

    act(() => result.current.setInputValue("hello"));
    act(() =>
      result.current.handleKeyDown({
        key: "Enter",
        shiftKey: true,
        preventDefault: vi.fn(),
      } as any)
    );
    await act(() => Promise.resolve());

    expect(onSend).not.toHaveBeenCalled();
  });

  it("calls onSendComplete after successful send", async () => {
    const onSendComplete = vi.fn();
    const { result } = renderChatInput({ onSendComplete });

    act(() => result.current.setInputValue("hello"));
    await act(() => result.current.handleSend());

    expect(onSendComplete).toHaveBeenCalledOnce();
  });

  it("calls onEditComplete after successful edit", async () => {
    const onEditComplete = vi.fn();
    const messages: Message[] = [
      { id: "1", role: "user", content: "original", sequence: 0, created_at: "" },
    ];
    const { result } = renderChatInput({ onEditComplete, messages });

    act(() => result.current.handleEdit());
    await act(() => result.current.handleSend());

    expect(onEditComplete).toHaveBeenCalledOnce();
  });

  it("handleEdit does nothing when no user messages exist", () => {
    const { result } = renderChatInput({ messages: emptyMessages });

    act(() => result.current.handleEdit());

    expect(result.current.inputValue).toBe("");
    expect(result.current.isEditingMode).toBe(false);
  });
});
