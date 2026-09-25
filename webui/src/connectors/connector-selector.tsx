import { Loader2, GitBranch, Link as LinkIcon } from "lucide-react";
import { Label } from "../ui/label.tsx";
import { Button } from "../ui/button.tsx";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select.tsx";
import { Input } from "../ui/input.tsx";
import { type ConnectorResource, type Connector } from "../lib/api.ts";

interface ConnectorSelectorProps {
  inputMode: "select" | "paste";
  setInputMode: (mode: "select" | "paste") => void;
  connectors: Connector[];
  selectedConnector: string;
  setSelectedConnector: (connector: string) => void;
  isLoadingConnectors: boolean;
  selectedResource: string;
  setSelectedResource: (resource: string) => void;
  resourceLink: string;
  setResourceLink: (link: string) => void;
  resources: ConnectorResource[];
  isLoadingResources: boolean;
  isLoadingTree: boolean;
  onResourceSelect: (resource: string) => void;
  onLinkPaste: (link: string) => void;
}

export function ConnectorSelector({
  inputMode,
  setInputMode,
  connectors,
  selectedConnector,
  setSelectedConnector,
  isLoadingConnectors,
  selectedResource,
  setSelectedResource,
  resourceLink,
  setResourceLink,
  resources,
  isLoadingResources,
  isLoadingTree,
  onResourceSelect,
  onLinkPaste,
}: ConnectorSelectorProps) {
  const handleResourceChange = (resource: string) => {
    setSelectedResource(resource);
    onResourceSelect(resource);
  };

  const handleLinkKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && resourceLink.trim()) {
      onLinkPaste(resourceLink);
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="connector">Connector Instance</Label>
        {isLoadingConnectors ? (
          <div className="flex items-center justify-center py-2">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : (
          <Select value={selectedConnector} onValueChange={setSelectedConnector}>
            <SelectTrigger id="connector">
              <SelectValue placeholder="Select a connector" />
            </SelectTrigger>
            <SelectContent>
              {connectors.map((c) => (
                <SelectItem key={c.name} value={c.name}>
                  <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4" />
                    <span>{c.name}</span>
                    <span className="text-xs opacity-50">({c.type})</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="space-y-2">
        {inputMode === "select" ? (
          <div className="space-y-2">
            <Label htmlFor="resource">Resource</Label>
            <div className="flex gap-2 items-center">
              {isLoadingResources ? (
                <div className="flex-1 flex items-center justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin" />
                </div>
              ) : (
                <Select value={selectedResource} onValueChange={handleResourceChange} disabled={!selectedConnector}>
                  <SelectTrigger id="resource" className="flex-1">
                    <SelectValue placeholder={selectedConnector ? "Select a resource" : "Select a connector first"} />
                  </SelectTrigger>
                  <SelectContent>
                    {resources.map((resource) => (
                      <SelectItem key={resource.id} value={resource.full_name}>
                        <div className="flex flex-col items-start">
                          <span className="font-medium">{resource.full_name}</span>
                          {resource.description && (
                            <span className="text-xs opacity-70 truncate max-w-[300px]">
                              {resource.description}
                            </span>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9"
                onClick={() => setInputMode("paste")}
                title={`Paste link`}
                disabled={!selectedConnector}
              >
                <LinkIcon className="h-4 w-4" />
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <Label htmlFor="resource-link">Resource Link</Label>
            <Input
              id="resource-link"
              placeholder="Resource identifier (e.g. owner/repo)"
              value={resourceLink}
              onChange={(e) => setResourceLink(e.target.value)}
              onKeyDown={handleLinkKeyDown}
              autoFocus
              disabled={!selectedConnector}
            />
          </div>
        )}
        {isLoadingTree && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading resource...
          </div>
        )}
      </div>
    </div>
  );
}
