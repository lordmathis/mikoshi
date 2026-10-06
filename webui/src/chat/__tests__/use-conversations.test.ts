import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useConversations } from "../use-conversations.ts";
import { api, type Chat } from "../../lib/api.ts";

function chat(id: string, minutesAgo: number, workspaceId: string | null = null): Chat {
  const at = new Date(Date.now() - minutesAgo * 60000).toISOString();
  return {
    id,
    title: id,
    created_at: at,
    updated_at: at,
    workspace_id: workspaceId,
  };
}

function fullPage(prefix: string, startMinute: number): Chat[] {
  return Array.from({ length: 20 }, (_, i) => chat(`${prefix}-${i}`, startMinute + i));
}

describe("useConversations", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(api, "listChats").mockResolvedValue({ chats: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches page 0 for the active workspace on mount", async () => {
    const listChats = vi.mocked(api.listChats);
    listChats.mockResolvedValue({ chats: fullPage("a", 0) });

    const { result } = renderHook(({ ws }) => useConversations(ws), {
      initialProps: { ws: "ws-1" },
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(listChats).toHaveBeenCalledWith(20, 0, "ws-1");
    expect(result.current.conversations).toHaveLength(20);
    expect(result.current.hasMore).toBe(true);
  });

  it("hasMore is false when the page is not full", async () => {
    vi.mocked(api.listChats).mockResolvedValue({ chats: [chat("only", 0)] });

    const { result } = renderHook(() => useConversations(null));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasMore).toBe(false);
  });

  it("loadMore fetches the next offset and collapses duplicate ids", async () => {
    const page0 = fullPage("a", 0);
    let call = 0;
    const listChats = vi.mocked(api.listChats).mockImplementation(() => {
      call++;
      if (call === 1) return Promise.resolve({ chats: page0 });
      // offset shift: a-19 reappears on page 2 alongside 19 new chats
      return Promise.resolve({
        chats: [page0[19], ...Array.from({ length: 19 }, (_, i) => chat(`b-${i}`, 20 + i))],
      });
    });

    const { result } = renderHook(() => useConversations(null));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => result.current.loadMore());
    await waitFor(() => expect(listChats).toHaveBeenLastCalledWith(20, 20, null));

    expect(result.current.conversations).toHaveLength(39);
    expect(result.current.conversations.filter((c) => c.id === "a-19")).toHaveLength(1);

    const sorted = [...result.current.conversations].sort((a, b) =>
      b.updated_at.localeCompare(a.updated_at)
    );
    expect(result.current.conversations.map((c) => c.id)).toEqual(sorted.map((c) => c.id));
  });

  it("workspace change resets pagination and fetches the new slice", async () => {
    const listChats = vi.mocked(api.listChats);
    listChats.mockResolvedValueOnce({ chats: fullPage("a", 0) });
    listChats.mockResolvedValueOnce({ chats: [chat("w1", 0, "ws-1")] });

    const { result, rerender } = renderHook(({ ws }) => useConversations(ws), {
      initialProps: { ws: null as string | null },
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.conversations).toHaveLength(20);

    rerender({ ws: "ws-1" });
    await waitFor(() =>
      expect(result.current.conversations.map((c) => c.id)).toEqual(["w1"])
    );
    expect(listChats).toHaveBeenLastCalledWith(20, 0, "ws-1");
    expect(result.current.hasMore).toBe(false);
  });

  it("upsertConversation prepends without duplicating", async () => {
    vi.mocked(api.listChats).mockResolvedValue({ chats: fullPage("a", 0) });

    const { result } = renderHook(() => useConversations(null));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => result.current.upsertConversation(chat("deep-link", 500)));
    expect(result.current.conversations[0].id).toBe("deep-link");
    expect(result.current.conversations).toHaveLength(21);

    act(() => result.current.upsertConversation(chat("deep-link", 500)));
    expect(result.current.conversations).toHaveLength(21);
    expect(result.current.conversations.filter((c) => c.id === "deep-link")).toHaveLength(1);
  });

  it("paints the cached list synchronously on mount, then revalidates in the background", async () => {
    localStorage.setItem(
      "mikoshi-cache:conversations",
      JSON.stringify([{ id: "cached-1", title: "Cached", timestamp: "now", updated_at: "2026-01-01T00:00:00Z" }])
    );
    vi.mocked(api.listChats).mockResolvedValue({ chats: [chat("fresh", 0)] });

    const { result } = renderHook(() => useConversations(null));

    expect(result.current.conversations.map((c) => c.id)).toEqual(["cached-1"]);

    await waitFor(() =>
      expect(result.current.conversations.map((c) => c.id)).toEqual(["fresh", "cached-1"])
    );
  });

  it("writes the merged list to the cache after fetching", async () => {
    vi.mocked(api.listChats).mockResolvedValue({ chats: [chat("fresh", 0)] });

    const { result } = renderHook(() => useConversations(null));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const stored = JSON.parse(
      localStorage.getItem("mikoshi-cache:conversations") ?? "[]"
    ) as { id: string }[];
    expect(stored.map((c) => c.id)).toEqual(["fresh"]);
  });

  it("keys the cache per workspace", async () => {
    vi.mocked(api.listChats).mockResolvedValue({ chats: [chat("w1", 0, "ws-1")] });

    const { result } = renderHook(() => useConversations("ws-1"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(localStorage.getItem("mikoshi-cache:conversations:ws-1")).not.toBeNull();
    expect(localStorage.getItem("mikoshi-cache:conversations")).toBeNull();
  });
});
