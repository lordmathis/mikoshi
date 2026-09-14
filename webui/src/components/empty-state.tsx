import type { ReactNode } from "react";

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="py-12 text-center cp-label opacity-20 italic">{children}</div>
  );
}
