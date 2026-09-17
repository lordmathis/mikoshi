import { Loader2 } from "lucide-react";

interface SelectionSummaryProps {
  selectedPaths: Set<string>;
  tokenEstimate: number | null;
  isEstimatingTokens?: boolean;
}

export function SelectionSummary({ selectedPaths, tokenEstimate, isEstimatingTokens = false }: SelectionSummaryProps) {
  const includedCount = Array.from(selectedPaths).filter((p) => !p.startsWith("!")).length;
  const excludedCount = Array.from(selectedPaths).filter((p) => p.startsWith("!")).length;

  if (includedCount === 0) return null;

  return (
    <div className="flex items-center justify-between text-sm bg-muted p-3 rounded-md">
      <span>
        <strong>{includedCount}</strong> item{includedCount !== 1 ? "s" : ""} selected
        {excludedCount > 0 && ` (${excludedCount} excluded)`}
      </span>
      {isEstimatingTokens ? (
        <span className="text-muted-foreground flex items-center gap-1.5">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Estimating tokens...
        </span>
      ) : tokenEstimate !== null ? (
        <span className="text-muted-foreground">~{tokenEstimate.toLocaleString()} tokens</span>
      ) : null}
    </div>
  );
}
