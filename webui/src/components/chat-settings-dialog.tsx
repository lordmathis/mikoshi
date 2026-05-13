import { useState, useEffect } from "react";
import { Settings, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Switch } from "./ui/switch";
import { Input } from "./ui/input";
import { api, type Model, type ToolServer, type ModelParams, type AgentConfig } from "../lib/api";

export interface ChatSettings {
  baseModel: string;
  systemPrompt: string;
  enabledTools: string[];
  modelParams: ModelParams;
}

interface ChatSettingsDialogProps {
  settings: ChatSettings;
  onSettingsChange: (settings: ChatSettings) => void;
  currentChatId?: string;
  onChatUpdated?: () => void;
}

export function ChatSettingsDialog({
  settings,
  onSettingsChange,
  currentChatId,
  onChatUpdated,
}: ChatSettingsDialogProps) {
  const [open, setOpen] = useState(false);
  const [localSettings, setLocalSettings] = useState<ChatSettings>(settings);
  const [modelsByProvider, setModelsByProvider] = useState<Record<string, { id: string; label: string }[]>>({});
  const [providers, setProviders] = useState<string[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [toolServers, setToolServers] = useState<ToolServer[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [isLoadingTools, setIsLoadingTools] = useState(false);
  const [agentConfigs, setAgentConfigs] = useState<AgentConfig[]>([]);
  const [toolsExpanded, setToolsExpanded] = useState(false);

  useEffect(() => {
    setLocalSettings(settings);
  }, [settings]);

  useEffect(() => {
    if (!open) return;

    let fetchedAgents: AgentConfig[] = [];
    let fetchedModels: Record<string, { id: string; label: string }[]> = {};
    let fetchedProviders: string[] = [];

    const loadAgents = async () => {
      try {
        const response = await api.listAgents();
        setAgentConfigs(response.agents);
        fetchedAgents = response.agents;
      } catch (error) {
        console.error("Failed to fetch agents:", error);
      }
    };

    const loadModels = async () => {
      try {
        setIsLoadingModels(true);
        const response = await api.listModels();

        const grouped: Record<string, { id: string; label: string }[]> = {};
        response.data
          .filter((model: Model) => model.owned_by !== "mikoshi")
          .forEach((model: Model) => {
            const provider = model.owned_by || "Unknown";
            if (!grouped[provider]) {
              grouped[provider] = [];
            }
            grouped[provider].push({
              id: model.id,
              label: model.id.includes(":") ? model.id.split(":").slice(1).join(":") : model.id,
            });
          });

        fetchedModels = grouped;
        fetchedProviders = Object.keys(grouped).sort();
        setModelsByProvider(grouped);
        setProviders(fetchedProviders);
      } catch (error) {
        console.error("Failed to fetch models:", error);
        setModelsByProvider({});
        setProviders([]);
      } finally {
        setIsLoadingModels(false);
      }
    };

    const loadTools = async () => {
      try {
        setIsLoadingTools(true);
        const response = await api.listTools();
        setToolServers(response.tool_servers);
      } catch (error) {
        console.error("Failed to fetch tools:", error);
        setToolServers([]);
      } finally {
        setIsLoadingTools(false);
      }
    };

    void Promise.all([loadTools(), loadAgents(), loadModels()]).then(() => {
      const baseModel = settings.baseModel;

      if (baseModel) {
        const agent = fetchedAgents.find((a) => a.name === baseModel);
        if (agent) {
          setSelectedAgent(agent.name);
          setSelectedProvider(agent.provider);
          setLocalSettings((prev) => ({
            ...prev,
            baseModel: `${agent.provider}:${agent.model_id}`,
          }));
        } else if (baseModel.includes(":")) {
          setSelectedProvider(baseModel.split(":")[0]);
        } else if (fetchedProviders.length > 0) {
          setSelectedProvider(fetchedProviders[0]);
        }
      } else if (fetchedProviders.length > 0) {
        setSelectedProvider(fetchedProviders[0]);
        const firstModel = fetchedModels[fetchedProviders[0]]?.[0];
        if (firstModel) {
          setLocalSettings((prev) => ({ ...prev, baseModel: firstModel.id }));
        }
      }

      setToolsExpanded(false);
    });

    return () => {
      setSelectedAgent("");
    };
  }, [open, settings]);

  const handleSave = async () => {
    let modelToSend = localSettings.baseModel;

    if (selectedAgent) {
      const agent = agentConfigs.find((a) => a.name === selectedAgent);
      if (agent && localSettings.baseModel === `${agent.provider}:${agent.model_id}`) {
        modelToSend = selectedAgent;
      }
    }

    onSettingsChange({
      ...localSettings,
      baseModel: modelToSend,
    });

    if (currentChatId) {
      try {
        await api.updateChat(currentChatId, {
          config: {
            model: modelToSend,
            system_prompt: localSettings.systemPrompt || undefined,
            tool_servers: localSettings.enabledTools.length > 0 ? localSettings.enabledTools : undefined,
            model_params: localSettings.modelParams,
          },
        });
        onChatUpdated?.();
      } catch (error) {
        console.error("Failed to update chat settings:", error);
        alert(`Failed to update chat settings: ${error instanceof Error ? error.message : "Unknown error"}`);
        return;
      }
    }

    setOpen(false);
  };

  const handleCancel = () => {
    setLocalSettings(settings);
    setOpen(false);
  };

  const toggleTool = (toolId: string) => {
    setLocalSettings((prev) => ({
      ...prev,
      enabledTools: prev.enabledTools.includes(toolId)
        ? prev.enabledTools.filter((id) => id !== toolId)
        : [...prev.enabledTools, toolId],
    }));
  };

  const handleAgentChange = (value: string) => {
    setSelectedAgent(value);
    const agent = agentConfigs.find((a) => a.name === value);
    if (agent) {
      setLocalSettings((prev) => ({
        ...prev,
        baseModel: `${agent.provider}:${agent.model_id}`,
        systemPrompt: agent.system_prompt,
        enabledTools: agent.tool_servers,
        modelParams: {
          ...prev.modelParams,
          max_iterations: agent.max_iterations,
          temperature: agent.temperature ?? prev.modelParams.temperature,
          max_tokens: agent.max_tokens ?? prev.modelParams.max_tokens,
        },
      }));
      setSelectedProvider(agent.provider);
    }
  };

  const handleProviderChange = (value: string) => {
    setSelectedProvider(value);
    const modelsForProvider = modelsByProvider[value] || [];
    if (modelsForProvider.length > 0) {
      setLocalSettings((prev) => ({ ...prev, baseModel: modelsForProvider[0].id }));
    }
  };

  const handleModelChange = (value: string) => {
    setLocalSettings((prev) => ({ ...prev, baseModel: value }));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Settings className="h-5 w-5" />
          <span className="sr-only">Chat settings</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="uppercase tracking-[0.15em] text-sm text-primary">Chat Configuration</DialogTitle>
          <DialogDescription className="cp-label">
            Configure agent, model, system prompt, and tools for this session.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Agent Selection */}
          <div className="space-y-2">
            <Label htmlFor="agent">Agent</Label>
            <Select value={selectedAgent || undefined} onValueChange={handleAgentChange}>
              <SelectTrigger id="agent" className="w-full">
                <SelectValue placeholder="Select an agent..." />
              </SelectTrigger>
              <SelectContent>
                {agentConfigs.map((agent) => (
                  <SelectItem key={agent.name} value={agent.name}>
                    {agent.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Applies a preset for system prompt, tools, and model. Everything can be overridden below.
            </p>
          </div>

          {/* Provider Selection */}
          <div className="space-y-2">
            <Label htmlFor="provider">Provider</Label>
            <Select
              value={selectedProvider}
              onValueChange={handleProviderChange}
              disabled={isLoadingModels}
            >
              <SelectTrigger id="provider" className="w-full">
                <SelectValue placeholder={isLoadingModels ? "Loading providers..." : "Select a provider"} />
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider} value={provider}>
                    {provider}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Model Selection */}
          <div className="space-y-2">
            <Label htmlFor="base-model">Model</Label>
            <Select
              value={localSettings.baseModel}
              onValueChange={handleModelChange}
              disabled={isLoadingModels || !selectedProvider}
            >
              <SelectTrigger id="base-model" className="w-full">
                <SelectValue placeholder={isLoadingModels ? "Loading models..." : "Select a model"} />
              </SelectTrigger>
              <SelectContent>
                {(modelsByProvider[selectedProvider] || []).map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {model.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* System Prompt */}
          <div className="space-y-2">
            <Label htmlFor="system-prompt">System Prompt</Label>
            <Textarea
              id="system-prompt"
              value={localSettings.systemPrompt}
              onChange={(e) =>
                setLocalSettings((prev) => ({
                  ...prev,
                  systemPrompt: e.target.value,
                }))
              }
              placeholder="Enter system prompt..."
              className="min-h-[120px] resize-none"
              rows={6}
            />
            <p className="text-xs text-muted-foreground">
              The system prompt sets the behavior and context for the AI
              assistant.
            </p>
          </div>

          {/* Model Parameters Section */}
          <div className="space-y-4">
            <div>
              <Label className="text-xs uppercase tracking-[0.15em] text-primary">Model Parameters</Label>
              <p className="cp-label mt-1">
                Configure advanced model behavior settings.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="max-iterations">Max Iterations</Label>
                <Input
                  id="max-iterations"
                  type="number"
                  min="1"
                  value={localSettings.modelParams.max_iterations ?? 5}
                  onChange={(e) => {
                    const value = e.target.value === "" ? undefined : parseInt(e.target.value);
                    setLocalSettings((prev) => ({
                      ...prev,
                      modelParams: {
                        ...prev.modelParams,
                        max_iterations: value,
                      },
                    }));
                  }}
                  placeholder="5"
                />
                <p className="text-xs text-muted-foreground">
                  Maximum tool call iterations
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="temperature">Temperature</Label>
                <Input
                  id="temperature"
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  value={localSettings.modelParams.temperature ?? ""}
                  onChange={(e) => {
                    const value = e.target.value === "" ? undefined : parseFloat(e.target.value);
                    setLocalSettings((prev) => ({
                      ...prev,
                      modelParams: {
                        ...prev.modelParams,
                        temperature: value,
                      },
                    }));
                  }}
                  placeholder="Default"
                />
                <p className="text-xs text-muted-foreground">
                  Randomness (0-2, lower = focused)
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="max-tokens">Max Tokens</Label>
                <Input
                  id="max-tokens"
                  type="number"
                  min="1"
                  value={localSettings.modelParams.max_tokens ?? ""}
                  onChange={(e) => {
                    const value = e.target.value === "" ? undefined : parseInt(e.target.value);
                    setLocalSettings((prev) => ({
                      ...prev,
                      modelParams: {
                        ...prev.modelParams,
                        max_tokens: value,
                      },
                    }));
                  }}
                  placeholder="Default"
                />
                <p className="text-xs text-muted-foreground">
                  Maximum response length
                </p>
              </div>
            </div>
          </div>

          {/* Tools Section - Collapsible */}
          <div className="space-y-4">
            <button
              type="button"
              onClick={() => setToolsExpanded(!toolsExpanded)}
              className="flex items-center gap-2 w-full text-left"
            >
              {toolsExpanded ? (
                <ChevronDown className="h-4 w-4 text-primary" />
              ) : (
                <ChevronRight className="h-4 w-4 text-primary" />
              )}
              <Label className="text-xs uppercase tracking-[0.15em] text-primary cursor-pointer">
                Tool Servers
              </Label>
              <span className="text-xs text-muted-foreground">
                ({localSettings.enabledTools.length} enabled)
              </span>
            </button>

            {toolsExpanded && (
              isLoadingTools ? (
                <div className="rounded-lg border border-border p-4 text-center text-sm text-muted-foreground">
                  Loading available tools...
                </div>
              ) : toolServers.length === 0 ? (
                <div className="rounded-lg border border-border p-4 text-center text-sm text-muted-foreground">
                  No tool servers available
                </div>
              ) : (
                <div className="space-y-3 rounded-lg border border-border p-4">
                  {toolServers.map((server) => (
                    <div
                      key={server.name}
                      className="flex items-center justify-between space-x-4"
                    >
                      <div className="flex-1 space-y-0.5">
                        <Label
                          htmlFor={`tool-${server.name}`}
                          className="cursor-pointer font-medium"
                        >
                          {server.name}
                        </Label>
                        <p className="text-sm text-muted-foreground">
                          {server.tools.length} tool{server.tools.length !== 1 ? 's' : ''} available ({server.type})
                        </p>
                      </div>
                      <Switch
                        id={`tool-${server.name}`}
                        checked={localSettings.enabledTools.includes(server.name)}
                        onCheckedChange={() => toggleTool(server.name)}
                      />
                    </div>
                  ))}
                </div>
              )
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save Changes</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
