import { ChevronDown, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Label } from "../ui/label.tsx";

interface CollapsibleSectionProps {
  title: string;
  expanded: boolean;
  onToggle: () => void;
  headerExtra?: ReactNode;
  children: ReactNode;
}

export function CollapsibleSection({
  title,
  expanded,
  onToggle,
  headerExtra,
  children,
}: CollapsibleSectionProps) {
  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-2 w-full text-left"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-primary" />
        ) : (
          <ChevronRight className="h-4 w-4 text-primary" />
        )}
        <Label className="text-xs uppercase tracking-[0.15em] text-primary cursor-pointer">
          {title}
        </Label>
        {headerExtra}
      </button>

      {expanded && children}
    </div>
  );
}
