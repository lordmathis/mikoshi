import { Download } from "lucide-react";
import { Chip } from "../shared/chip.tsx";
import type { FileResource } from "../lib/api.ts";

export function FileChip({ file }: { file: FileResource }) {
  return (
    <a href={`/api/files/${file.id}/download`} download={file.filename}>
      <Chip
        className="text-xs border-border bg-primary/6 hover:border-primary/40 transition-colors"
        icon={<Download className="h-3.5 w-3.5 text-primary/60" />}
        label={file.filename}
        labelClassName="font-medium text-foreground/80"
      />
    </a>
  );
}
