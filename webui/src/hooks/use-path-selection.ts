import { useState, useMemo } from "react";
import type { FileNode } from "../lib/api";

function findNode(node: FileNode, path: string): FileNode | null {
  if (node.path === path) return node;
  if (node.children) {
    for (const child of node.children) {
      const found = findNode(child, path);
      if (found) return found;
    }
  }
  return null;
}

export function usePathSelection(
  initialPaths: string[],
  initialExcludePaths: string[]
) {
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => {
    const initial = new Set<string>(initialPaths);
    initialExcludePaths.forEach((path) => initial.add(`!${path}`));
    return initial;
  });

  const getAllPathsInDir = (node: FileNode): string[] => {
    const paths = [node.path];
    if (node.children) {
      node.children.forEach((child) => {
        paths.push(...getAllPathsInDir(child));
      });
    }
    return paths;
  };

  const isPathSelectedIn = (path: string, paths: Set<string>): boolean => {
    if (paths.has(path)) return true;
    if (path === "") return false;
    if (paths.has("")) return true;
    const pathParts = path.split("/");
    for (let i = 1; i < pathParts.length; i++) {
      const parentPath = pathParts.slice(0, i).join("/");
      if (paths.has(parentPath)) return true;
    }
    return false;
  };

  const isPathSelected = (path: string): boolean => isPathSelectedIn(path, selectedPaths);

  const isPathExcluded = (path: string): boolean => {
    return selectedPaths.has(`!${path}`);
  };

  const toggleSelect = (path: string, isDir: boolean, treeRoot: FileNode | null) => {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      const isCurrentlySelected = isPathSelectedIn(path, prev);
      const isCurrentlyExcluded = prev.has(`!${path}`);

      if (isCurrentlySelected && !next.has(path)) {
        next.add(`!${path}`);
      } else if (isCurrentlyExcluded) {
        next.delete(`!${path}`);
      } else if (next.has(path)) {
        next.delete(path);

        if (isDir && treeRoot) {
          const dirNode = findNode(treeRoot, path);
          if (dirNode) {
            const allPaths = getAllPathsInDir(dirNode);
            allPaths.forEach((p) => {
              next.delete(`!${p}`);
            });
          }
        }
      } else {
        next.add(path);

        if (isDir && treeRoot) {
          const dirNode = findNode(treeRoot, path);
          if (dirNode) {
            const allPaths = getAllPathsInDir(dirNode);
            allPaths.forEach((p) => {
              next.delete(`!${p}`);
            });
          }
        }
      }

      return next;
    });
  };

  const includedPaths = useMemo(() => {
    const paths: string[] = [];
    selectedPaths.forEach((path) => {
      if (!path.startsWith("!")) {
        paths.push(path);
      }
    });
    return paths;
  }, [selectedPaths]);

  const excludedPaths = useMemo(() => {
    const paths: string[] = [];
    selectedPaths.forEach((path) => {
      if (path.startsWith("!")) {
        paths.push(path.substring(1));
      }
    });
    return paths;
  }, [selectedPaths]);

  return {
    selectedPaths,
    isPathSelected,
    isPathExcluded,
    toggleSelect,
    includedPaths,
    excludedPaths,
  };
}