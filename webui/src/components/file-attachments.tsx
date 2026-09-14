import { File, Link as LinkIcon, X } from "lucide-react";
import type { ConnectorEntry, FileResource } from "../lib/api";
import { Chip } from "./chip";

interface FileAttachmentsProps {
  uploadedFiles: FileResource[];
  connectorEntries: ConnectorEntry[];
  onRemoveFile: (fileId: string) => void;
  onRemoveConnectorEntry: (connectorId: string, resourceId: string) => void;
  onEditConnectorEntry: (connectorId: string, resourceId: string) => void;
}

export function FileAttachments({
  uploadedFiles,
  connectorEntries,
  onRemoveFile,
  onRemoveConnectorEntry,
  onEditConnectorEntry,
}: FileAttachmentsProps) {
  if (uploadedFiles.length === 0 && connectorEntries.length === 0) {
    return null;
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      {uploadedFiles.map((f, index) => (
        <Chip
          key={`${f.id}-${index}`}
          className="text-xs"
          style={{
            borderColor: "rgb(var(--cp-rgb-yellow) / 0.2)",
            background: "rgb(var(--cp-rgb-yellow) / 0.06)",
          }}
          icon={<File className="h-3.5 w-3.5 text-primary/70" />}
          label={f.filename}
          labelClassName="text-primary font-medium"
          actions={
            <button
              onClick={() => onRemoveFile(f.id)}
              className="ml-1 hover:text-[var(--color-cp-red)] transition-colors"
              aria-label={`Remove ${f.filename}`}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          }
        />
      ))}

      {connectorEntries.map((entry) => {
        const label = entry.resourceId.includes('/')
          ? entry.resourceId.split('/')[1]
          : entry.resourceId;

        return (
          <Chip
            key={`${entry.connectorId}-${entry.resourceId}`}
            className="text-xs"
            style={{
              borderColor: "rgb(var(--cp-rgb-cyan) / 0.2)",
              background: "rgb(var(--cp-rgb-cyan) / 0.06)",
            }}
            icon={<LinkIcon className="h-3.5 w-3.5 text-[var(--color-cp-cyan)]" />}
            labelClassName="text-[var(--color-cp-cyan)] font-medium"
            label={
              <>
                {entry.files.length} file{entry.files.length !== 1 ? "s" : ""} from{" "}
                {label}
              </>
            }
            actions={
              <>
                <button
                  onClick={() => onEditConnectorEntry(entry.connectorId, entry.resourceId)}
                  className="ml-1 hover:text-[var(--color-cp-cyan)]/80 transition-colors"
                  aria-label="Edit connector entry"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                  </svg>
                </button>
                <button
                  onClick={() => onRemoveConnectorEntry(entry.connectorId, entry.resourceId)}
                  className="ml-1 hover:text-[var(--color-cp-red)] transition-colors"
                  aria-label="Remove connector entry"
                  title="Remove connector entry"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </>
            }
          />
        );
      })}
    </div>
  );
}
