import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChatRoute } from "../use-chat-route.ts";

function setPath(path: string) {
  window.history.replaceState({}, "", path);
}

function firePopState() {
  act(() => {
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
}

describe("useChatRoute", () => {
  beforeEach(() => {
    setPath("/");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("parses the chat id from the url on load", () => {
    setPath("/chat/abc-123");
    const { result } = renderHook(() => useChatRoute());
    expect(result.current.chatId).toBe("abc-123");
  });

  it("returns null for unknown paths", () => {
    setPath("/");
    expect(renderHook(() => useChatRoute()).result.current.chatId).toBeNull();

    setPath("/chat/");
    expect(renderHook(() => useChatRoute()).result.current.chatId).toBeNull();

    setPath("/chat/abc/extra");
    expect(renderHook(() => useChatRoute()).result.current.chatId).toBeNull();

    setPath("/somewhere/else");
    expect(renderHook(() => useChatRoute()).result.current.chatId).toBeNull();
  });

  it("navigate pushes a history entry, updates state and url", () => {
    const pushSpy = vi.spyOn(window.history, "pushState");
    const { result } = renderHook(() => useChatRoute());

    act(() => result.current.navigate("abc"));

    expect(result.current.chatId).toBe("abc");
    expect(window.location.pathname).toBe("/chat/abc");
    expect(pushSpy).toHaveBeenCalledTimes(1);
  });

  it("navigate with replace swaps the entry without pushing", () => {
    setPath("/chat/dead-chat");
    const pushSpy = vi.spyOn(window.history, "pushState");
    const replaceSpy = vi.spyOn(window.history, "replaceState");
    const { result } = renderHook(() => useChatRoute());

    act(() => result.current.navigate(null, { replace: true }));

    expect(result.current.chatId).toBeNull();
    expect(window.location.pathname).toBe("/");
    expect(replaceSpy).toHaveBeenCalledTimes(1);
    expect(pushSpy).not.toHaveBeenCalled();
  });

  it("keeps state in sync with popstate", () => {
    const { result } = renderHook(() => useChatRoute());

    act(() => result.current.navigate("abc"));
    expect(result.current.chatId).toBe("abc");

    // back button: URL reverts and the browser fires popstate
    setPath("/");
    firePopState();
    expect(result.current.chatId).toBeNull();
  });
});
