import { useState, useEffect, useCallback } from "react";

function parseChatId(pathname: string): string | null {
  const match = pathname.match(/^\/chat\/([\w-]+)$/);
  return match ? match[1] : null;
}

export function useChatRoute() {
  const [chatId, setChatId] = useState<string | null>(() =>
    parseChatId(window.location.pathname)
  );

  useEffect(() => {
    const onPopState = () => setChatId(parseChatId(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((id: string | null, opts?: { replace?: boolean }) => {
    const url = id ? `/chat/${id}` : "/";
    if (opts?.replace) {
      window.history.replaceState({}, "", url);
    } else {
      window.history.pushState({}, "", url);
    }
    setChatId(id);
  }, []);

  return { chatId, navigate };
}
