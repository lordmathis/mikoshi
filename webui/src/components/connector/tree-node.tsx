import { Folder, File, ChevronRight, ChevronDown, Loader2 } from "lucide-react";
import { Checkbox } from "../ui/checkbox";
import { type FileNode } from "../../lib/api";

interface TreeNodeProps {
  node: FileNode;
  level: number;
  selectedPaths: Set<string>;
  expandedPaths: Set<string>;
  onToggleSelect: (path: string, isDir: boolean) => void;
  onToggleExpand: (path: string) => void;
  onLoadChildren: (path: string) => void;
  loadingPaths: Set<string>;
  isPathSelected: (path: string) => boolean;
  isPathExcluded: (path: string) => boolean;
}

export function TreeNode({
  node,
  level,
  selectedPaths,
  expandedPaths,
  onToggleSelect,
  onToggleExpand,
  onLoadChildren,
  loadingPaths,
  isPathSelected,
  isPathExcluded,
}: TreeNodeProps) {
  const isExpanded = expandedPaths.has(node.path);
  const isLoading = loadingPaths.has(node.path);
  const isSelected = isPathSelected(node.path);
  const isExcluded = isPathExcluded(node.path);
  const isDir = node.type === "dir";

  const handleToggle = () => {
    if (isDir) {
      if (!isExpanded && !node.children) {
        onLoadChildren(node.path);
      }
      onToggleExpand(node.path);
    }
  };

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1.5 px-2 hover:bg-accent hover:text-accent-foreground rounded-md cursor-pointer"
        style={{ paddingLeft: `${level * 20 + 8}px` }}
      >
        {isDir && (
          <button
            onClick={handleToggle}
            className="flex items-center justify-center w-4 h-4 hover:bg-accent-foreground/10 rounded"
          >
            {isLoading ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : isExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        )}
        {!isDir && <div className="w-4" />}
        <Checkbox
          checked={isSelected && !isExcluded}
          onCheckedChange={() => onToggleSelect(node.path, isDir)}
          className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
        />
        {isDir ? (
          <Folder className="h-4 w-4 text-blue-500 flex-shrink-0" />
        ) : (
          <File className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        )}
        <span className="text-sm truncate min-w-0 flex-1" onClick={handleToggle}>
          {node.name}
        </span>
        {!isDir && node.size !== undefined && (
          <span className="text-xs text-muted-foreground ml-auto">
            {(node.size / 1024).toFixed(1)} KB
          </span>
        )}
      </div>
      {isDir && isExpanded && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              level={level + 1}
              selectedPaths={selectedPaths}
              expandedPaths={expandedPaths}
              onToggleSelect={onToggleSelect}
              onToggleExpand={onToggleExpand}
              onLoadChildren={onLoadChildren}
              loadingPaths={loadingPaths}
              isPathSelected={isPathSelected}
              isPathExcluded={isPathExcluded}
            />
          ))}
        </div>
      )}
    </div>
  );
}
