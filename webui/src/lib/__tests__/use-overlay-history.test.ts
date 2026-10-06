import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useOverlayHistory } from "../use-overlay-history.ts";

function mockDesktop(desktop: boolean) {
  return vi
    .spyOn(window, "matchMedia")
    .mockReturnValue({ matches: desktop } as MediaQueryList);
}

describe("useOverlayHistory", () => {
  beforeEach(() => {
    history.replaceState(null, "");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("pushes a history entry when opened on mobile", () => {
    mockDesktop(false);
    const onClose = vi.fn();

    const { rerender } = renderHook(
      ({ isOpen }) => useOverlayHistory(isOpen, onClose),
      { initialProps: { isOpen: false } }
    );
    expect(history.state).toBeNull();

    rerender({ isOpen: true });
    expect(history.state).toEqual({ mOverlay: true });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes on popstate while open", () => {
    mockDesktop(false);
    const onClose = vi.fn();

    const { rerender } = renderHook(
      ({ isOpen }) => useOverlayHistory(isOpen, onClose),
      { initialProps: { isOpen: false } }
    );
    rerender({ isOpen: true });

    history.back();
    expect(onClose).not.toHaveBeenCalled(); // popstate is async

    return new Promise<void>((resolve) => {
      window.addEventListener("popstate", () => {
        expect(onClose).toHaveBeenCalledOnce();
        resolve();
      });
    });
  });

  it("consumes the history entry when closed via the UI", async () => {
    mockDesktop(false);
    const onClose = vi.fn();

    const { rerender } = renderHook(
      ({ isOpen }) => useOverlayHistory(isOpen, onClose),
      { initialProps: { isOpen: false } }
    );
    rerender({ isOpen: true });
    rerender({ isOpen: false });

    await waitFor(() =>
      expect(history.state).not.toEqual({ mOverlay: true })
    );
  });

  it("does nothing on lg viewports", () => {
    mockDesktop(true);
    const onClose = vi.fn();

    const { rerender } = renderHook(
      ({ isOpen }) => useOverlayHistory(isOpen, onClose),
      { initialProps: { isOpen: false } }
    );
    rerender({ isOpen: true });

    expect(history.state).toBeNull();
  });
});
