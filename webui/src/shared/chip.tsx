import type { CSSProperties, ReactNode } from "react";
import { cn } from "../lib/utils.ts";

interface ChipProps {
  icon: ReactNode;
  label: ReactNode;
  className?: string;
  style?: CSSProperties;
  labelClassName?: string;
  labelStyle?: CSSProperties;
  actions?: ReactNode;
}

export function Chip({
  icon,
  label,
  className,
  style,
  labelClassName,
  labelStyle,
  actions,
}: ChipProps) {
  return (
    <div
      className={cn("flex items-center gap-1.5 border px-2 py-1 cp-cut-8", className)}
      style={style}
    >
      {icon}
      <span className={labelClassName} style={labelStyle}>
        {label}
      </span>
      {actions}
    </div>
  );
}
