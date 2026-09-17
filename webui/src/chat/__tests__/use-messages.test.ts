import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useMessages } from "../use-messages.ts";
import { api, type Message, type StreamEvent } from "../../lib/api.ts";

function chat(id: string, messages: Message[]) {
  return {
    id,
    title: id,
    created_at: "",
    updated_at: "",
    messages,
  };
}

function message(id: string, role: Message["role"], content: string): Message {
  return { id, role, content, sequence: 0, created_at: "" };
}

function manualStream() {
  const queue: StreamEvent[] = [];
  let wakeup: (() => void) | undefined;
  let finished = false;
  return {
    push(event: StreamEvent) {
      queue.push(event);
      wakeup?.();
    },
    end() {
      finished = true;
      wakeup?.();
    },
    stream: async function* (): AsyncGenerator<StreamEvent> {
      while (true) {
        if (queue.length > 0) {
          yield queue.shift()!;
        } else if (finished) {
          return;
        } else {
          await new Promise<void>((resolve) => {
            wakeup = resolve;
          });
        }
      }
    },
  };
}

describe("useMessages", () => {
  beforeEach(() => {
    vi.spyOn(api, "getChat").mockResolvedValue(chat("chat-a", []));
    vi.spyOn(api, "listApprovals").mockResolvedValue({ approvals: [] });
    vi.spyOn(api, "getStreamStatus").mockResolvedValue({ active: false });
    vi.spyOn(api, "getDefaultChatConfig").mockResolvedValue({ tool_servers: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not append old chat's stream events after switching chats", async () => {
    const manual = manualStream();
    const streamMessage = vi
      .spyOn(api, "streamMessage")
      .mockImplementation(async function* (_chatId, _data, signal) {
        expect(signal).toBeInstanceOf(AbortSignal);
        yield* manual.stream();
      });

    const { result, rerender } = renderHook(
      ({ id }) => useMessages(id),
      { initialProps: { id: "chat-a" as string | undefined } }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    let sendPromise: Promise<void> | undefined;
    act(() => {
      sendPromise = result.current.send("hello", []);
    });
    await waitFor(() =>
      expect(result.current.messages.some((m) => m.content === "hello")).toBe(true)
    );
    expect(streamMessage).toHaveBeenCalledWith(
      "chat-a",
      expect.objectContaining({ message: "hello" }),
      expect.any(AbortSignal)
    );

    vi.mocked(api.getChat).mockResolvedValue(chat("chat-b", [message("b1", "user", "b msg")]));
    rerender({ id: "chat-b" });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.messages.map((m) => m.id)).toEqual(["b1"]);

    // Old chat's stream is aborted and its events must not bleed into chat-b
    const signal = streamMessage.mock.calls[0][2]!;
    expect(signal.aborted).toBe(true);
    await act(async () => {
      manual.push({ type: "message", data: message("a-reply", "assistant", "old chat reply") });
    });
    expect(result.current.messages.map((m) => m.id)).toEqual(["b1"]);

    await act(async () => {
      manual.end();
      await sendPromise;
    });
  });

  it("stops loading and reports an error when fetching a chat fails", async () => {
    vi.spyOn(api, "getChat").mockRejectedValue(new Error("network down"));

    const { result } = renderHook(() => useMessages("chat-x"));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.loadError).toBe("network down");
    expect(result.current.messages).toEqual([]);
  });
});
