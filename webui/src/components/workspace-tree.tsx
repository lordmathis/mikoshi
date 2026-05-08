import { useState, useEffect, useCallback } from "react";
import { Folder, File, ChevronRight, ChevronDown, Loader2 } from "lucide-react";
import { api, type FileNode } from "../lib/api";

interface WorkspaceTreeProps {
  tree: FileNode | null;
  activeFilePath: string | null;
  onFileClick: (path: string) => void;
  workspaceId?: string | null;
}

function TreeNode({
  node,
  level,
  activeFilePath,
  onFileClick,
  onLoadChildren,
  loadingPaths,
}: {
  node: FileNode;
  level: number;
  activeFilePath: string | null;
  onFileClick: (path: string) => void;
  onLoadChildren: (path: string) => void;
  loadingPaths: Set<string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const isDir = node.type === "dir";
  const isActive = activeFilePath === node.path;
  const isLoading = loadingPaths.has(node.path);

  const handleClick = () => {
    if (isDir) {
      if (!expanded && !node.children) {
        onLoadChildren(node.path);
      }
      setExpanded(!expanded);
    } else {
      onFileClick(node.path);
    }
  };

  return (
    <div>
      <div
        className={`flex items-center gap-2 py-1 px-2 rounded-md cursor-pointer transition-colors ${
          isActive
            ? "bg-primary/10 text-primary"
            : "hover:bg-accent hover:text-accent-foreground"
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={handleClick}
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
        <span className="text-sm truncate">{node.name}</span>
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
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function WorkspaceTree({ tree, activeFilePath, onFileClick, workspaceId }: WorkspaceTreeProps) {
  const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
  const [localTree, setLocalTree] = useState<FileNode | null>(tree);

  useEffect(() => {
    setLocalTree(tree);
  }, [tree]);

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
    [tree, workspaceId]
  );

  if (!localTree) {
    return (
      <div className="py-12 text-center cp-label opacity-20 italic">
        No files loaded
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      {(localTree.children || []).map((child) => (
        <TreeNode
          key={child.path}
          node={child}
          level={0}
          activeFilePath={activeFilePath}
          onFileClick={onFileClick}
          onLoadChildren={loadChildren}
          loadingPaths={loadingPaths}
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
