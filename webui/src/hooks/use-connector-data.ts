import { useState, useEffect } from "react";
import { api, type ConnectorResource, type FileNode, type Connector, type FileResource } from "../lib/api";
import { fetchAllFilePaths, matchesPatterns } from "../lib/connector-utils";

const sortChildren = (children: FileNode[]): FileNode[] => {
  return [...children].sort((a, b) => {
    const aIsDir = a.type === "dir";
    const bIsDir = b.type === "dir";
    if (aIsDir && !bIsDir) return -1;
    if (!aIsDir && bIsDir) return 1;
    return a.name.localeCompare(b.name);
  });
};

const sortTree = (node: FileNode): FileNode => {
  if (node.children) {
    return { ...node, children: sortChildren(node.children).map(sortTree) };
  }
  return node;
};

export function useConnectorData(
  initialInstance: string,
  initialConnector: string,
  includedPaths: string[],
  excludedPaths: string[]
) {
  const [inputMode, setInputMode] = useState<"select" | "paste">("select");
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [selectedConnector, setSelectedConnector] = useState<string>(initialInstance);
  const [isLoadingConnectors, setIsLoadingConnectors] = useState(false);
  const [resources, setResources] = useState<ConnectorResource[]>([]);
  const [selectedResource, setSelectedResource] = useState<string>(initialConnector);
  const [resourceLink, setResourceLink] = useState<string>(initialConnector);
  const [isLoadingResources, setIsLoadingResources] = useState(false);
  const [isLoadingTree, setIsLoadingTree] = useState(false);
  const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
  const [treeRoot, setTreeRoot] = useState<FileNode | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState<string>("");
  const [tokenEstimate, setTokenEstimate] = useState<number | null>(null);
  const [isEstimatingTokens, setIsEstimatingTokens] = useState(false);
  const [filterPattern, setFilterPattern] = useState("");
  const [isApplyingFilter, setIsApplyingFilter] = useState(false);

  const parseConnectorLink = (link: string): string | null => {
    try {
      const match = link.match(/github\.com[:/]([^/]+\/[^/\s.]+)/);
      if (match) {
        return match[1].replace(/\.git$/, "");
      }
      if (/^[^/]+\/[^/]+$/.test(link.trim())) {
        return link.trim();
      }
      return null;
    } catch {
      return null;
    }
  };

  const getResourceIdentifier = (): string => {
    if (inputMode === "select") {
      return selectedResource;
    } else {
      const parsed = parseConnectorLink(resourceLink);
      return parsed || "";
    }
  };

  const loadConnectors = async () => {
    try {
      setIsLoadingConnectors(true);
      setError("");
      const response = await api.listConnectors();
      setConnectors(response.connectors);
      if (response.connectors.length > 0 && !selectedConnector) {
        setSelectedConnector(response.connectors[0].name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load connectors");
    } finally {
      setIsLoadingConnectors(false);
    }
  };

  const loadResources = async () => {
    if (!selectedConnector) return;
    try {
      setIsLoadingResources(true);
      setError("");
      const response = await api.listConnectorResources(selectedConnector);
      setResources(response.resources);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load resources");
    } finally {
      setIsLoadingResources(false);
    }
  };

  const loadChildren = async (path: string) => {
    const resource = getResourceIdentifier();
    if (!resource || !treeRoot || !selectedConnector) return;

    try {
      setLoadingPaths((prev) => new Set(prev).add(path));
      const subtree = await api.browseConnectorTree(selectedConnector, resource, path);

      setTreeRoot((prev) => {
        if (!prev) return prev;
        const updateNode = (node: FileNode): FileNode => {
          if (node.path === path) {
            return { ...node, children: subtree.children ? sortChildren(subtree.children) : undefined };
          }
          if (node.children) {
            return { ...node, children: node.children.map(updateNode) };
          }
          return node;
        };
        return updateNode(prev);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load directory");
    } finally {
      setLoadingPaths((prev) => {
        const next = new Set(prev);
        next.delete(path);
        return next;
      });
    }
  };

  const toggleExpand = (path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleResourceSelect = async (resource: string) => {
    setSelectedResource(resource);
    setInputMode("select");

    try {
      setIsLoadingTree(true);
      setError("");
      const tree = await api.browseConnectorTree(selectedConnector, resource, "");
      setTreeRoot(sortTree(tree));
      setExpandedPaths(new Set([tree.path]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load resource tree");
      setTreeRoot(null);
    } finally {
      setIsLoadingTree(false);
    }
  };

  const handleLinkPaste = async (link: string) => {
    const parsed = parseConnectorLink(link);
    if (!parsed) {
      setError("Invalid resource link");
      return;
    }

    setResourceLink(link);

    try {
      setIsLoadingTree(true);
      setError("");
      const tree = await api.browseConnectorTree(selectedConnector, parsed, "");
      setTreeRoot(sortTree(tree));
      setExpandedPaths(new Set([tree.path]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load resource tree");
      setTreeRoot(null);
    } finally {
      setIsLoadingTree(false);
    }
  };

  const uploadFiles = async (paths: string[], excludePaths: string[]): Promise<FileResource[]> => {
    const resource = getResourceIdentifier();
    if (!resource) {
      setError("Please select or enter a valid resource");
      throw new Error("Please select or enter a valid resource");
    }

    if (paths.length === 0) {
      setError("Please select at least one file or folder");
      throw new Error("Please select at least one file or folder");
    }

    try {
      setIsAdding(true);
      setError("");

      const fileResources = await api.uploadConnectorFiles(selectedConnector, resource, paths, excludePaths);
      return fileResources;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add files");
      throw err;
    } finally {
      setIsAdding(false);
    }
  };

  const applyFilter = async (
    toggleSelect: (path: string, isDir: boolean, treeRoot: FileNode | null) => void,
    treeRoot: FileNode | null,
    isPathSelected: (path: string) => boolean,
    isPathExcluded: (path: string) => boolean
  ) => {
    if (!filterPattern.trim() || !treeRoot) return;
    const resource = getResourceIdentifier();
    if (!resource || !selectedConnector) return;

    try {
      setIsApplyingFilter(true);
      setError("");
      const allPaths = await fetchAllFilePaths(selectedConnector, resource);
      for (const path of allPaths) {
        if (matchesPatterns(path, filterPattern) && isPathSelected(path) && !isPathExcluded(path)) {
          toggleSelect(path, false, treeRoot);
        }
      }
      setFilterPattern("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply filter");
    } finally {
      setIsApplyingFilter(false);
    }
  };

  // Estimate tokens when selection changes
  useEffect(() => {
    const estimateTokens = async () => {
      const resource = getResourceIdentifier();
      if (!resource || includedPaths.length === 0 || !selectedConnector) {
        setTokenEstimate(null);
        setIsEstimatingTokens(false);
        return;
      }

      try {
        setIsEstimatingTokens(true);
        const estimate = await api.estimateConnectorTokens(selectedConnector, resource, includedPaths, excludedPaths);
        setTokenEstimate(estimate.total_tokens);
      } catch (err) {
        console.error("Token estimation error:", err);
        setTokenEstimate(null);
      } finally {
        setIsEstimatingTokens(false);
      }
    };

    estimateTokens();
  }, [includedPaths, excludedPaths, inputMode, selectedResource, resourceLink, selectedConnector]);

  // Load connectors on mount
  useEffect(() => {
    loadConnectors();
  }, []);

  // Load resources when connector changes
  useEffect(() => {
    if (selectedConnector) {
      loadResources();
    }
  }, [selectedConnector]);

  return {
    inputMode,
    setInputMode,
    connectors,
    selectedConnector,
    setSelectedConnector,
    resources,
    selectedResource,
    setSelectedResource,
    resourceLink,
    setResourceLink,
    isLoadingConnectors,
    isLoadingResources,
    isLoadingTree,
    loadingPaths,
    treeRoot,
    expandedPaths,
    isAdding,
    error,
    tokenEstimate,
    isEstimatingTokens,
    filterPattern,
    setFilterPattern,
    isApplyingFilter,
    applyFilter,
    getResourceIdentifier,
    loadResources,
    loadChildren,
    toggleExpand,
    handleResourceSelect,
    handleLinkPaste,
    uploadFiles,
  };
}