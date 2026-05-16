import { useState, useEffect, useCallback, useRef } from "react";
import { Folder, File, ChevronRight, ChevronDown, Loader2, Pencil, Trash2, Plus, ArrowDownFromLine, ArrowUpFromLine, Check } from "lucide-react";
import { api, type FileNode } from "../lib/api";
import { useGit } from "../hooks/use-git";

interface WorkspaceTreeProps {
  tree: FileNode | null;
  activeFilePath: string | null;
  onFileClick: (path: string) => void;
  workspaceId?: string | null;
  onRefreshTree: () => Promise<void>;
  onFileDeleted: (path: string) => void;
  onFileRenamed: (oldPath: string, newPath: string) => void;
}

function TreeNode({
  node,
  level,
  activeFilePath,
  onFileClick,
  onLoadChildren,
  loadingPaths,
  onRefreshTree,
  onFileDeleted,
  onFileRenamed,
  workspaceId,
}: {
  node: FileNode;
  level: number;
  activeFilePath: string | null;
  onFileClick: (path: string) => void;
  onLoadChildren: (path: string) => void;
  loadingPaths: Set<string>;
  onRefreshTree: () => Promise<void>;
  onFileDeleted: (path: string) => void;
  onFileRenamed: (oldPath: string, newPath: string) => void;
  workspaceId?: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(node.name);
  const [isDragOver, setIsDragOver] = useState(false);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const isDir = node.type === "dir";
  const isActive = activeFilePath === node.path;
  const isLoading = loadingPaths.has(node.path);

  useEffect(() => {
    if (isRenaming && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [isRenaming]);

  const handleClick = () => {
    if (isRenaming) return;
    if (isDir) {
      if (!expanded && !node.children) {
        onLoadChildren(node.path);
      }
      setExpanded(!expanded);
    } else {
      onFileClick(node.path);
    }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!workspaceId) return;
    try {
      await api.deleteWorkspaceFile(workspaceId, node.path);
      onFileDeleted(node.path);
      await onRefreshTree();
    } catch (err) {
      console.error("Failed to delete file:", err);
    }
  };

  const handleRenameStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    setRenameValue(node.name);
    setIsRenaming(true);
  };

  const handleRenameConfirm = async () => {
    setIsRenaming(false);
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === node.name) return;
    const newPath = node.path.slice(0, -node.name.length) + trimmed;
    if (!workspaceId) return;
    try {
      const result = await api.renameWorkspaceFile(workspaceId, node.path, newPath);
      onFileRenamed(node.path, result.new_path);
      await onRefreshTree();
    } catch (err) {
      console.error("Failed to rename file:", err);
    }
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleRenameConfirm();
    } else if (e.key === "Escape") {
      setIsRenaming(false);
    }
  };

  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData("text/plain", node.path);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent) => {
    if (!isDir) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDragEnter = (e: React.DragEvent) => {
    if (!isDir) return;
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (!isDir) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
      setIsDragOver(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (!isDir || !workspaceId) return;
    const srcPath = e.dataTransfer.getData("text/plain");
    if (!srcPath || srcPath === node.path) return;
    if (node.path !== "" && srcPath.startsWith(node.path + "/")) return;
    const fileName = srcPath.split("/").pop()!;
    const newPath = node.path ? `${node.path}/${fileName}` : fileName;
    if (newPath === srcPath) return;
    try {
      const result = await api.renameWorkspaceFile(workspaceId, srcPath, newPath);
      onFileRenamed(srcPath, result.new_path);
      await onRefreshTree();
    } catch (err) {
      console.error("Failed to move file:", err);
    }
  };

  return (
    <div>
      <div
        className={`group flex items-center gap-2 py-1 px-2 rounded-md cursor-pointer transition-colors ${
          isDragOver
            ? "bg-primary/15 ring-1 ring-primary/40"
            : isActive
              ? "bg-primary/10 text-primary"
              : "hover:bg-accent hover:text-accent-foreground"
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={handleClick}
        draggable={!isDir}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isDir ? (
          <button className="flex items-center justify-center w-4 h-4">
            {isLoading ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        ) : (
          <div className="w-4" />
        )}
        {isDir ? (
          <Folder className="h-4 w-4 text-blue-500 flex-shrink-0" />
        ) : (
          <File className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        )}
        {isRenaming ? (
          <input
            ref={renameInputRef}
            className="text-sm bg-transparent border-b border-primary outline-none flex-1 min-w-0"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={handleRenameKeyDown}
            onBlur={handleRenameConfirm}
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="text-sm truncate min-w-0 flex-1">{node.name}</span>
        )}
        {!isRenaming && (
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
            <button
              className="p-0.5 rounded hover:bg-accent/80 [&:hover>svg]:text-accent-foreground"
              onClick={handleRenameStart}
              title="Rename"
            >
              <Pencil className="h-3 w-3 text-primary-foreground transition-transform hover:scale-110" />
            </button>
            {!isDir && (
              <button
                className="p-0.5 rounded hover:bg-accent/80 [&:hover>svg]:text-accent-foreground"
                onClick={handleDelete}
                title="Delete"
              >
                <Trash2 className="h-3 w-3 text-primary-foreground transition-transform hover:scale-110" />
              </button>
            )}
          </div>
        )}
      </div>
      {isDir && expanded && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              level={level + 1}
              activeFilePath={activeFilePath}
              onFileClick={onFileClick}
              onLoadChildren={onLoadChildren}
              loadingPaths={loadingPaths}
              onRefreshTree={onRefreshTree}
              onFileDeleted={onFileDeleted}
              onFileRenamed={onFileRenamed}
              workspaceId={workspaceId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function WorkspaceTree({ tree, activeFilePath, onFileClick, workspaceId, onRefreshTree, onFileDeleted, onFileRenamed }: WorkspaceTreeProps) {
  const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
  const [localTree, setLocalTree] = useState<FileNode | null>(tree);
  const [isCreating, setIsCreating] = useState(false);
  const [newFileName, setNewFileName] = useState("");
  const [isRootDragOver, setIsRootDragOver] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [commitMessage, setCommitMessage] = useState("");
  const [flashBtn, setFlashBtn] = useState<string | null>(null);
  const [shakeBtn, setShakeBtn] = useState<string | null>(null);
  const newFileInputRef = useRef<HTMLInputElement>(null);
  const commitInputRef = useRef<HTMLInputElement>(null);
  const git = useGit(workspaceId ?? null);

  useEffect(() => {
    setLocalTree(tree);
  }, [tree]);

  useEffect(() => {
    if (isCreating && newFileInputRef.current) {
      newFileInputRef.current.focus();
    }
  }, [isCreating]);

  useEffect(() => {
    if (isCommitting && commitInputRef.current) {
      commitInputRef.current.focus();
    }
  }, [isCommitting]);

  useEffect(() => {
    if (!flashBtn) return;
    const t = setTimeout(() => setFlashBtn(null), 300);
    return () => clearTimeout(t);
  }, [flashBtn]);

  useEffect(() => {
    if (!shakeBtn) return;
    const t = setTimeout(() => setShakeBtn(null), 300);
    return () => clearTimeout(t);
  }, [shakeBtn]);

  const loadChildren = useCallback(
    async (path: string) => {
      if (!workspaceId) return;
      setLoadingPaths((prev) => new Set(prev).add(path));
      try {
        const node = await api.getWorkspaceTree(workspaceId, path);
        setLocalTree((prev) => {
          if (!prev) return prev;
          return mergeChildren(prev, path, node.children || []);
        });
      } catch (error) {
        console.error("Failed to load tree children:", error);
      } finally {
        setLoadingPaths((prev) => {
          const next = new Set(prev);
          next.delete(path);
          return next;
        });
      }
    },
    [workspaceId]
  );

  const handleCreateFile = async () => {
    const trimmed = newFileName.trim();
    if (!trimmed || !workspaceId) return;
    setIsCreating(false);
    setNewFileName("");
    try {
      await api.createWorkspaceFile(workspaceId, trimmed);
      await onRefreshTree();
      onFileClick(trimmed);
    } catch (err) {
      console.error("Failed to create file:", err);
    }
  };

  const handleNewFileKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleCreateFile();
    } else if (e.key === "Escape") {
      setIsCreating(false);
      setNewFileName("");
    }
  };

  const handleGitPull = async () => {
    const result = await git.pull();
    if (result.success) {
      setFlashBtn("pull");
      await onRefreshTree();
    } else {
      setShakeBtn("pull");
    }
  };

  const handleGitPush = async () => {
    const result = await git.push();
    if (result.success) {
      setFlashBtn("push");
    } else {
      setShakeBtn("push");
    }
  };

  const handleCommitKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      const msg = commitMessage.trim();
      if (!msg) return;
      setIsCommitting(false);
      setCommitMessage("");
      git.commit(msg).then((result) => {
        if (result.success) {
          setFlashBtn("commit");
          onRefreshTree();
        } else {
          setShakeBtn("commit");
        }
      });
    } else if (e.key === "Escape") {
      setIsCommitting(false);
      setCommitMessage("");
    }
  };

  const btnClass = (id: string) =>
    `p-1 rounded hover:bg-accent transition-colors [&:hover>svg]:text-accent-foreground ${flashBtn === id ? "cp-flash-success" : ""} ${shakeBtn === id ? "cp-shake-error" : ""}`;

  if (!localTree) {
    return (
      <div className="py-12 text-center cp-label opacity-20 italic">
        No files loaded
      </div>
    );
  }

  return (
    <div
      className={`space-y-0.5 rounded-md transition-colors ${isRootDragOver ? "bg-primary/10 ring-1 ring-primary/30" : ""}`}
      onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }}
      onDragEnter={() => setIsRootDragOver(true)}
      onDragLeave={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const { clientX: x, clientY: y } = e;
        if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
          setIsRootDragOver(false);
        }
      }}
      onDrop={async (e) => {
        e.preventDefault();
        setIsRootDragOver(false);
        if (!workspaceId) return;
        const srcPath = e.dataTransfer.getData("text/plain");
        if (!srcPath) return;
        const fileName = srcPath.split("/").pop()!;
        if (fileName === srcPath) return;
        try {
          const result = await api.renameWorkspaceFile(workspaceId, srcPath, fileName);
          onFileRenamed(srcPath, result.new_path);
          await onRefreshTree();
        } catch (err) {
          console.error("Failed to move file:", err);
        }
      }}
    >
      <div className="flex items-center justify-end px-1 pb-1 gap-0.5">
        <button
          className={btnClass("pull")}
          onClick={handleGitPull}
          disabled={git.isLoading}
          title={git.status ? `Pull (branch: ${git.status.branch})` : "Pull"}
        >
          {git.isLoading && flashBtn !== "pull" && shakeBtn !== "pull" ? (
            <Loader2 className="h-3.5 w-3.5 text-foreground animate-spin" />
          ) : (
            <ArrowDownFromLine className="h-3.5 w-3.5 text-foreground" />
          )}
        </button>
        <button
          className={btnClass("push")}
          onClick={handleGitPush}
          disabled={git.isLoading}
          title={git.status ? `Push (branch: ${git.status.branch})` : "Push"}
        >
          {git.isLoading && flashBtn !== "push" && shakeBtn !== "push" ? (
            <Loader2 className="h-3.5 w-3.5 text-foreground animate-spin" />
          ) : (
            <ArrowUpFromLine className="h-3.5 w-3.5 text-foreground" />
          )}
        </button>
        <button
          className={btnClass("commit")}
          onClick={() => setIsCommitting(true)}
          disabled={git.isLoading}
          title="Commit"
        >
          <Check className="h-3.5 w-3.5 text-foreground" />
        </button>
        <button
          className="p-1 rounded hover:bg-accent transition-colors [&:hover>svg]:text-accent-foreground"
          onClick={() => setIsCreating(true)}
          title="New file"
        >
          <Plus className="h-3.5 w-3.5 text-foreground" />
        </button>
      </div>
      {isCommitting && (
        <div className="flex items-center gap-2 py-1 px-2 rounded-md bg-accent/50">
          <Check className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          <input
            ref={commitInputRef}
            className="text-sm bg-transparent border-b border-primary outline-none flex-1 min-w-0"
            placeholder="commit message"
            value={commitMessage}
            onChange={(e) => setCommitMessage(e.target.value)}
            onKeyDown={handleCommitKeyDown}
            onBlur={() => {
              if (!commitMessage.trim()) {
                setIsCommitting(false);
              }
            }}
          />
        </div>
      )}
      {isCreating && (
        <div className="flex items-center gap-2 py-1 px-2 rounded-md bg-accent/50">
          <File className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          <input
            ref={newFileInputRef}
            className="text-sm bg-transparent border-b border-primary outline-none flex-1 min-w-0"
            placeholder="filename.txt"
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            onKeyDown={handleNewFileKeyDown}
            onBlur={() => {
              if (!newFileName.trim()) {
                setIsCreating(false);
              }
            }}
          />
        </div>
      )}
      {(localTree.children || []).map((child) => (
        <TreeNode
          key={child.path}
          node={child}
          level={0}
          activeFilePath={activeFilePath}
          onFileClick={onFileClick}
          onLoadChildren={loadChildren}
          loadingPaths={loadingPaths}
          onRefreshTree={onRefreshTree}
          onFileDeleted={onFileDeleted}
          onFileRenamed={onFileRenamed}
          workspaceId={workspaceId}
        />
      ))}
    </div>
  );
}

function mergeChildren(root: FileNode, targetPath: string, children: FileNode[]): FileNode {
  if (root.path === targetPath) {
    return { ...root, children };
  }
  if (root.children) {
    return {
      ...root,
      children: root.children.map((child) =>
        targetPath.startsWith(child.path)
          ? mergeChildren(child, targetPath, children)
          : child
      ),
    };
  }
  return root;
}
