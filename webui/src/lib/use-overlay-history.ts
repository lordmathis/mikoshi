import { useEffect, useRef } from "react";

const DESKTOP_QUERY = "(min-width: 1024px)";

export function isDesktopViewport(): boolean {
  return window.matchMedia(DESKTOP_QUERY).matches;
}

/**
 * Android back-button support for mobile overlays: pushes a history entry
 * when the overlay opens on < lg so the back gesture closes the overlay
 * instead of leaving the app. Overlapping overlays must share one call:
 * concurrent entries race because history.back() traversals land on the
 * most recently pushed entry, not the caller's own.
 */
export function useOverlayHistory(isOpen: boolean, onClose: () => void) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen || isDesktopViewport()) return;

    history.pushState({ mOverlay: true }, "");
    const onPop = () => onCloseRef.current();
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      // Closed via the UI: consume our history entry so back doesn't
      // dead-end on it. A mid-stack navigation leaves the entry behind
      // as a harmless no-op.
      const state = history.state as { mOverlay?: boolean } | null;
      if (state?.mOverlay) history.back();
    };
  }, [isOpen]);
}
