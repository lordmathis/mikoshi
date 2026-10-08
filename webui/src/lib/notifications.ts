const MAX_BODY_CHARS = 120;

function truncateBody(body: string): string {
  const text = body.replace(/\s+/g, " ").trim();
  if (text.length <= MAX_BODY_CHARS) return text;
  return `${text.slice(0, MAX_BODY_CHARS - 1)}…`;
}

export const notifications = {
  requestPermission(): void {
    try {
      if ("Notification" in window && Notification.permission === "default") {
        void Notification.requestPermission();
      }
    } catch {
      // Notifications unsupported — best-effort.
    }
  },

  notifyWhenHidden(title: string, body: string): void {
    try {
      if (
        "Notification" in window &&
        Notification.permission === "granted" &&
        document.visibilityState !== "visible"
      ) {
        const notification = new Notification(title, { body: truncateBody(body) });
        notification.onclick = () => window.focus();
      }
    } catch {
      // Notifications unsupported — best-effort.
    }
  },
};
