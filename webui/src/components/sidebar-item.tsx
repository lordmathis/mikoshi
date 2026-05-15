import { Trash2 } from "lucide-react";
import { Button } from "./ui/button";

interface SidebarItemProps {
  id: string;
  isActive: boolean;
  label: string;
  sublabel?: string;
  badge?: string;
  clipPath?: string;
  confirmMessage: string;
  onClick: () => void;
  onDelete: () => void;
  children?: React.ReactNode;
}

export function SidebarItem({
  isActive,
  label,
  sublabel,
  badge,
  onClick,
  onDelete,
  confirmMessage,
  children,
}: SidebarItemProps) {
  return (
    <div
      className={`group relative flex items-center transition-all duration-200 cursor-pointer border cp-cut-br-8 ${
        isActive
          ? "bg-primary/5 border-primary/30 shadow-[0_0_15px_rgb(var(--cp-rgb-yellow)_/_0.05)]"
          : "bg-white/[0.02] border-white/5 hover:border-white/10 hover:bg-white/[0.04]"
      }`}
      onClick={onClick}
    >
      <div
        className={`absolute left-0 top-0 bottom-0 w-[2px] transition-all duration-300 ${
          isActive ? "bg-primary" : "bg-transparent group-hover:bg-white/20"
        }`}
      />

      <div className="flex-1 min-w-0 px-4 py-3">
        <div className="flex items-center justify-between mb-1">
          <div
            className={`text-[9px] font-bold tracking-widest ${
              isActive ? "text-cyan" : "text-muted-foreground"
            }`}
          >
            {sublabel}
          </div>
          <div className="flex items-center gap-2">
            {badge && (
              <span className="text-[8px] text-primary/50 uppercase">{badge}</span>
            )}
            {children}
          </div>
        </div>
        <div
          className={`truncate text-[13px] font-medium tracking-tight ${
            isActive ? "text-foreground" : "text-foreground/60"
          }`}
        >
          {label}
        </div>
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 mr-2 opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive"
        onClick={(e) => {
          e.stopPropagation();
          if (window.confirm(confirmMessage)) {
            onDelete();
          }
        }}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}
