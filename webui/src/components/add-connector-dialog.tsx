import { useEffect } from "react";
import { Loader2, Filter, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";
import { TreeNode } from "./connector/tree-node";
import { ConnectorSelector } from "./connector/connector-selector";
import { SelectionSummary } from "./connector/selection-summary";
import { usePathSelection } from "../hooks/use-path-selection";
import { useConnectorData } from "../hooks/use-connector-data";
import type { ConnectorEntry } from "../lib/api";

interface AddConnectorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  chatId?: string;
  onFilesAdded?: (entry: ConnectorEntry) => void;
  editingEntry?: ConnectorEntry;
}

export function AddConnectorDialog({
  open,
  onOpenChange,
  chatId,
  onFilesAdded,
  editingEntry,
}: AddConnectorDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
        {/* Mounted only while the dialog is open, so hook state is
            initialized from editingEntry fresh on every open */}
        <ConnectorDialogBody
          chatId={chatId}
          onOpenChange={onOpenChange}
          onFilesAdded={onFilesAdded}
          editingEntry={editingEntry}
        />
      </DialogContent>
    </Dialog>
  );
}

function ConnectorDialogBody({
  chatId,
  onOpenChange,
  onFilesAdded,
  editingEntry,
}: Omit<AddConnectorDialogProps, "open">) {
  const pathSelection = usePathSelection(
    editingEntry?.paths || [],
    editingEntry?.excludePaths || []
  );
  const connectorData = useConnectorData(
    editingEntry?.connectorId || "",
    editingEntry?.resourceId || "",
    pathSelection.includedPaths,
    pathSelection.excludedPaths
  );

  const handleToggleSelect = (path: string, isDir: boolean) =>
    pathSelection.toggleSelect(path, isDir, connectorData.treeRoot);

  const handleApplyFilter = () => {
    connectorData.applyFilter(
      handleToggleSelect,
      connectorData.treeRoot,
      pathSelection.isPathSelected,
      pathSelection.isPathExcluded
    );
  };

  useEffect(() => {
    if (connectorData.inputMode === "select" && connectorData.resources.length === 0 && connectorData.selectedConnector) {
      connectorData.loadResources();
    }
  }, [connectorData.inputMode, connectorData.selectedConnector, connectorData.resources.length]);

  const includedCount = Array.from(pathSelection.selectedPaths).filter(p => !p.startsWith("!")).length;

  const handleAdd = async () => {
    if (!chatId) return;
    
    try {
      const files = await connectorData.uploadFiles(
        pathSelection.includedPaths,
        pathSelection.excludedPaths
      );
      onFilesAdded?.({
        connectorId: connectorData.selectedConnector,
        resourceId: connectorData.getResourceIdentifier(),
        paths: pathSelection.includedPaths,
        excludePaths: pathSelection.excludedPaths,
        files,
      });
      onOpenChange(false);
    } catch {
      // Error already set in hook
    }
  };

  const handleClose = () => {
    onOpenChange(false);
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle className="uppercase tracking-[0.15em] text-sm text-primary">Add Connector Files</DialogTitle>
        <DialogDescription className="cp-label">
          Select files from a repository to add to your conversation
        </DialogDescription>
      </DialogHeader>

        <div className="flex-1 flex flex-col gap-4 overflow-hidden">
          <ConnectorSelector
            inputMode={connectorData.inputMode}
            setInputMode={connectorData.setInputMode}
            connectors={connectorData.connectors}
            selectedConnector={connectorData.selectedConnector}
            setSelectedConnector={connectorData.setSelectedConnector}
            isLoadingConnectors={connectorData.isLoadingConnectors}
            selectedResource={connectorData.selectedResource}
            setSelectedResource={connectorData.setSelectedResource}
            resourceLink={connectorData.resourceLink}
            setResourceLink={connectorData.setResourceLink}
            resources={connectorData.resources}
            isLoadingResources={connectorData.isLoadingResources}
            isLoadingTree={connectorData.isLoadingTree}
            onResourceSelect={connectorData.handleResourceSelect}
            onLinkPaste={connectorData.handleLinkPaste}
          />

          {connectorData.error && (
            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">{connectorData.error}</div>
          )}

          {connectorData.treeRoot && (
            <div className="flex-1 min-h-0 border rounded-md">
              <ScrollArea className="h-[300px] p-2">
                <TreeNode
                  node={connectorData.treeRoot}
                  level={0}
                  selectedPaths={pathSelection.selectedPaths}
                  expandedPaths={connectorData.expandedPaths}
                  onToggleSelect={handleToggleSelect}
                  onToggleExpand={connectorData.toggleExpand}
                  onLoadChildren={connectorData.loadChildren}
                  loadingPaths={connectorData.loadingPaths}
                  isPathSelected={pathSelection.isPathSelected}
                  isPathExcluded={pathSelection.isPathExcluded}
                />
              </ScrollArea>
            </div>
          )}

          {connectorData.treeRoot && (
            <div className="flex gap-2 items-center">
              <div className="relative flex-1">
                <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none z-10" />
                <Input
                  placeholder="Exclude by pattern, comma-separated (e.g. *.lock, uv.lock)"
                  value={connectorData.filterPattern}
                  onChange={(e) => connectorData.setFilterPattern(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleApplyFilter(); }}
                  className="pl-9 pr-9 focus-visible:ring-inset"
                />
                {connectorData.filterPattern && (
                  <button
                    onClick={() => connectorData.setFilterPattern("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground z-10"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <Button
                variant="outline"
                onClick={handleApplyFilter}
                disabled={!connectorData.filterPattern.trim() || connectorData.isApplyingFilter}
              >
                {connectorData.isApplyingFilter
                  ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Applying...</>
                  : "Exclude"}
              </Button>
            </div>
          )}

          <SelectionSummary selectedPaths={pathSelection.selectedPaths} tokenEstimate={connectorData.tokenEstimate} isEstimatingTokens={connectorData.isEstimatingTokens} />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={connectorData.isAdding}>
            Cancel
          </Button>
          <Button onClick={handleAdd} disabled={connectorData.isAdding || pathSelection.selectedPaths.size === 0 || !chatId}>
            {connectorData.isAdding ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Adding files...
              </>
            ) : (
              `Add ${includedCount} item${includedCount !== 1 ? "s" : ""}`
            )}
          </Button>
        </DialogFooter>
    </>
  );
}
