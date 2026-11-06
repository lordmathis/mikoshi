const TOAST_MS = 6000;
const CONTAINER_CLASS = "fixed bottom-4 right-4 z-[100] flex flex-col gap-2";
const TOAST_CLASS =
  "max-w-sm cursor-pointer border border-destructive bg-cp-surface3 text-foreground text-sm px-3 py-2 cp-cut-8 shadow-lg";

let container: HTMLDivElement | null = null;

function ensureContainer(): HTMLDivElement {
  if (!container || !document.body.contains(container)) {
    container = document.createElement("div");
    container.className = CONTAINER_CLASS;
    document.body.appendChild(container);
  }
  return container;
}

export function showError(message: string): void {
  const toast = document.createElement("div");
  toast.className = TOAST_CLASS;
  toast.textContent = message;
  toast.onclick = () => toast.remove();
  ensureContainer().appendChild(toast);
  window.setTimeout(() => toast.remove(), TOAST_MS);
}
