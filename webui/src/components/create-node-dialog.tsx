import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { api, type Connector } from "../lib/api";

interface CreateNodeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (workspace: { id: string; name: string }) => void;
}

export function CreateNodeDialog({ open, onOpenChange, onCreated }: CreateNodeDialogProps) {
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [connector, setConnector] = useState<string>("__none__");
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      api.listConnectors().then((res) => setConnectors(res.connectors)).catch(() => {});
      setName("");
      setRepoUrl("");
      setConnector("__none__");
      setError(null);
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsCreating(true);
    setError(null);
    try {
      const trimmedRepo = repoUrl.trim();
      const ws = await api.createWorkspace({
        name: name.trim(),
        repo_url: trimmedRepo ? trimmedRepo : undefined,
        connector: connector === "__none__" ? undefined : connector,
      });
      onCreated(ws);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create node");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="uppercase tracking-[0.15em] text-sm text-primary">
            Spawn Node
          </DialogTitle>
          <DialogDescription className="cp-label">
            Create a new workspace node. Add a repo URL to clone, or leave it empty for a local-only workspace.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="node-name">Name</Label>
            <Input
              id="node-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-project"
              disabled={isCreating}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="repo-url">Repo URL (optional)</Label>
            <Input
              id="repo-url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/org/repo.git"
              disabled={isCreating}
            />
          </div>

          {connectors.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="connector">Connector (optional)</Label>
              <Select value={connector} onValueChange={setConnector} disabled={isCreating}>
                <SelectTrigger id="connector">
                  <SelectValue placeholder="No auth" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">No auth</SelectItem>
                  {connectors.map((c) => (
                    <SelectItem key={c.name} value={c.name}>
                      {c.name} ({c.type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {error && (
            <div className="text-sm text-destructive border border-destructive/20 rounded-md px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isCreating}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isCreating || !name.trim()}
            >
              {isCreating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {repoUrl.trim() ? "Cloning..." : "Creating..."}
                </>
              ) : (
                "SPAWN_NODE"
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
