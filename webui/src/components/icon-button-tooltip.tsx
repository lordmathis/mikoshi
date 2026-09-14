import type { ReactNode } from "react";
import { Button } from "./ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";

interface IconButtonTooltipProps {
  icon: ReactNode;
  label: string;
  srLabel: string;
  onClick: () => void;
  disabled?: boolean;
  iconClassName?: string;
}

export function IconButtonTooltip({
  icon,
  label,
  srLabel,
  onClick,
  disabled,
  iconClassName,
}: IconButtonTooltipProps) {
  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onClick}
            disabled={disabled}
          >
            <span className={iconClassName}>{icon}</span>
            <span className="sr-only">{srLabel}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="left">
          <p>{label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
