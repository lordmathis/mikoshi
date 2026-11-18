import { ExternalLink } from "lucide-react";
import { encodeFilePath } from "../lib/api.ts";

interface PdfPreviewProps {
  workspaceId: string | null;
  filePath: string;
}

export function PdfPreview({ workspaceId, filePath }: PdfPreviewProps) {
  const src = workspaceId
    ? `/api/workspaces/${workspaceId}/files/${encodeFilePath(filePath)}`
    : null;
  const fileName = filePath.split("/").pop() || filePath;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div
        className="shrink-0 flex items-center justify-end px-4 py-1 border-b"
        style={{ borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)" }}
      >
        {src && (
          <a
            href={src}
            target="_blank"
            rel="noopener noreferrer"
            className="cp-label text-foreground/70 hover:text-primary inline-flex items-center gap-1 transition-colors"
          >
            <ExternalLink className="h-3 w-3" />
            Open in new tab
          </a>
        )}
      </div>
      {src && (
        <iframe src={src} title={fileName} className="flex-1 w-full bg-cp-surface3" />
      )}
    </div>
  );
}
