import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSidebar } from "../use-sidebar";

describe("useSidebar", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("defaults to sessions tab when no stored state", () => {
    const { result } = renderHook(() => useSidebar());
    expect(result.current.activeTab).toBe("sessions");
    expect(result.current.activeWorkspaceId).toBeNull();
  });

  it("persists tab change to sessionStorage", () => {
    const { result } = renderHook(() => useSidebar());

    act(() => result.current.setActiveTab("data"));

    const stored = JSON.parse(sessionStorage.getItem("mikoshi-sidebar")!);
    expect(stored.activeTab).toBe("data");
    expect(result.current.activeTab).toBe("data");
  });

  it("loads state from sessionStorage on init", () => {
    sessionStorage.setItem(
      "mikoshi-sidebar",
      JSON.stringify({ activeTab: "nodes", activeWorkspaceId: "ws-1" })
    );

    const { result } = renderHook(() => useSidebar());
    expect(result.current.activeTab).toBe("nodes");
    expect(result.current.activeWorkspaceId).toBe("ws-1");
  });

  it("falls back to defaults when sessionStorage has corrupted JSON", () => {
    sessionStorage.setItem("mikoshi-sidebar", "{not valid json");

    const { result } = renderHook(() => useSidebar());
    expect(result.current.activeTab).toBe("sessions");
    expect(result.current.activeWorkspaceId).toBeNull();
  });

  it("persists workspace change to sessionStorage", () => {
    const { result } = renderHook(() => useSidebar());

    act(() => result.current.setActiveWorkspace("ws-42"));

    const stored = JSON.parse(sessionStorage.getItem("mikoshi-sidebar")!);
    expect(stored.activeWorkspaceId).toBe("ws-42");
  });

  it("clears workspace when set to null", () => {
    sessionStorage.setItem(
      "mikoshi-sidebar",
      JSON.stringify({ activeTab: "sessions", activeWorkspaceId: "ws-1" })
    );

    const { result } = renderHook(() => useSidebar());
    act(() => result.current.setActiveWorkspace(null));

    const stored = JSON.parse(sessionStorage.getItem("mikoshi-sidebar")!);
    expect(stored.activeWorkspaceId).toBeNull();
  });
});
