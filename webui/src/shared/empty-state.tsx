import type { ReactNode } from "react";

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="py-12 text-center cp-label text-foreground/70 italic">{children}</div>
  );
}
