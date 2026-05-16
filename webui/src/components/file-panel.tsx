import { File, X, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { FilePreview } from "./file-preview";
import { FileEditor } from "./file-editor";
import { cn } from "../lib/utils";

interface FilePanelProps {
  filePath: string | null;
  fileContent: string | null;
  isLoading: boolean;
  onClose: () => void;
  workspaceId: string | null;
  fileIndex: Map<string, string>;
  onFileClick: (path: string) => void;
  mode: "preview" | "edit";
  setMode: (mode: "preview" | "edit") => void;
  editContent: string | null;
  setEditContent: (content: string) => void;
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
}

function isTextFile(path: string): boolean {
  return /\.(md|mdx|markdown|txt|json|js|ts|tsx|jsx|py|rs|go|toml|yaml|yml|xml|html|css|scss|sh|bash|zsh|cfg|ini|conf|env|gitignore|editorconfig|prettierrc|eslintrc|lock)$/i.test(path)
    || /^\.[a-z]/i.test(path.split("/").pop() || "");
}

export function FilePanel({
  filePath,
  fileContent,
  isLoading,
  onClose,
  workspaceId,
  fileIndex,
  onFileClick,
  mode,
  setMode,
  editContent,
  setEditContent,
  isDirty,
  isSaving,
  onSave,
}: FilePanelProps) {
  if (!filePath) return null;

  const fileName = filePath.split("/").pop() || filePath;
  const canEdit = fileContent !== null && isTextFile(filePath);

  return (
    <div className="flex flex-col h-full overflow-hidden border-r" style={{ borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)" }}>
      <div
        className="flex items-center justify-between px-4 py-2 shrink-0 border-b"
        style={{
          borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)",
          background: "rgb(var(--cp-rgb-surface3) / 0.95)",
        }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <File className="h-4 w-4 text-primary/60 flex-shrink-0" />
          <span className="cp-label text-foreground truncate">
            {fileName}
            {isDirty && <span className="text-primary/60 ml-0.5">*</span>}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            className={cn(
              "cp-label px-2 py-0.5 rounded transition-colors",
              mode === "preview"
                ? "text-primary bg-primary/10"
                : "text-foreground/50 hover:text-foreground/80"
            )}
            onClick={() => setMode("preview")}
          >
            Preview
          </button>
          <button
            className={cn(
              "cp-label px-2 py-0.5 rounded transition-colors",
              mode === "edit"
                ? "text-primary bg-primary/10"
                : canEdit
                  ? "text-foreground/50 hover:text-foreground/80"
                  : "text-foreground/20 cursor-not-allowed"
            )}
            onClick={() => {
              if (!canEdit) return;
              setEditContent(fileContent ?? "");
              setMode("edit");
            }}
            disabled={!canEdit}
          >
            Edit
          </button>
          <Button variant="ghost" size="icon" className="h-7 w-7 opacity-50 hover:opacity-100" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {mode === "preview" ? (
        <FilePreview
          filePath={filePath}
          fileContent={fileContent}
          isLoading={isLoading}
          onClose={onClose}
          workspaceId={workspaceId}
          fileIndex={fileIndex}
          onFileClick={onFileClick}
          hideHeader
        />
      ) : (
        <div className="flex flex-col flex-1 min-h-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-primary/50" />
            </div>
          ) : editContent !== null ? (
            <>
              <FileEditor
                content={editContent}
                onContentChange={setEditContent}
                onSave={onSave}
              />
              {isSaving && (
                <div className="shrink-0 px-4 py-1 border-t text-xs text-primary/60" style={{ borderColor: "rgb(var(--cp-rgb-yellow) / 0.1)" }}>
                  Saving...
                </div>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
