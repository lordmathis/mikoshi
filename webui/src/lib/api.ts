// API client for the backend
// Use /api prefix which gets proxied to the backend by Vite
//
// API Structure:
// - /api/chats/* - Chat management and messaging
// - /api/config/* - Configuration (models, agents, providers, default settings)
// - /api/connectors/* - Generic connector integration (GitHub, Forgejo, etc.)
// - /api/media/* - Media processing (transcription, etc.)
// - /api/skills/* - Skills management
// - /api/tools/* - Tool servers and tools
const API_BASE_URL = '/api';

export interface Chat {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  model?: string | null;
  system_prompt?: string | null;
  tool_servers?: string[] | null;
  model_params?: ModelParams | null;
  workspace_id?: string | null;
}

export interface FileResource {
  id: string;
  filename: string;
  content_type: string;
  source?: string | null;
}

export interface ConnectorEntry {
  connectorId: string;
  resourceId: string;
  paths: string[];
  excludePaths: string[];
  files: FileResource[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool' | 'error';
  content: string;
  reasoning_content?: string | null;
  tool_calls?: Array<{
    name: string;
    arguments: Record<string, any>;
  }> | null;
  tool_call_id?: string | null;
  sequence: number;
  created_at: string;
  files?: Array<{
    id: string;
    filename: string;
    content_type: string;
    source?: string | null;
  }>;
}

export interface WorkspaceChangeResult {
  __workspace: true;
  summary: string;
  paths: string[];
}

export interface StreamEvent {
  type: 'message' | 'error' | 'done';
  data: Message | { message: string } | Record<string, never>;
}

export interface ModelParams {
  max_iterations?: number;
  temperature?: number;
  max_tokens?: number;
}

export interface ChatWithMessages extends Chat {
  messages: Message[];
  tool_servers?: any;
  model_params?: ModelParams;
}

export interface ChatConfig {
  model: string;
  system_prompt?: string;
  tool_servers?: string[];
  model_params?: ModelParams;
}

export interface CreateChatRequest {
  title?: string;
  workspace_id?: string | null;
  config: ChatConfig;
}

export interface SendMessageRequest {
  message: string;
  file_ids?: string[];
  stream?: boolean;
}

export interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

export interface ToolServer {
  name: string;
  type: string;
  tools: Tool[];
}

export interface Tool {
  name: string;
  description: string;
  parameters?: any;
}

export interface Connector {
  name: string;         // e.g. "my-github-account"
  type: "github" | "forgejo";
}

export interface ConnectorResource {
  id: string | number;
  name: string;
  full_name: string;
  description: string | null;
}

export interface FileNode {
  path: string;
  name: string;
  type: 'file' | 'dir';
  size?: number;
  children?: FileNode[];
}

export interface Workspace {
  id: string;
  name: string;
  repo_url: string | null;
  connector: string | null;
  created_at: string;
  updated_at: string;
}

export interface TokenEstimate {
  total_tokens: number;
  files: Record<string, number>;
}

export interface AgentConfig {
  name: string;
  system_prompt: string;
  provider: string;
  model_id: string;
  tool_servers: string[];
  temperature: number | null;
  max_tokens: number | null;
  max_iterations: number;
}

export interface DefaultChatConfig {
  model?: string | null;
  system_prompt?: string | null;
  tool_servers: string[];
  model_params?: ModelParams | null;
}

export interface Skill {
  name: string;
  path: string;
  exists: boolean;
}

export interface GitStatus {
  branch: string;
  staged: number;
  unstaged: number;
  untracked: number;
}

export interface GitResult {
  success: boolean;
  output: string;
}

class ApiClient {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  private async assertOk(response: Response): Promise<void> {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
    }
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    await this.assertOk(response);

    return response.json();
  }

  // Chat endpoints
  async listChats(limit: number = 20): Promise<{ chats: Chat[] }> {
    return this.request(`/chats?limit=${limit}`);
  }

  async getChat(chatId: string): Promise<ChatWithMessages> {
    return this.request(`/chats/${chatId}`);
  }

  async getStreamStatus(chatId: string): Promise<{ active: boolean }> {
    return this.request(`/chats/${chatId}/stream-status`);
  }

  async *subscribeStream(chatId: string, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    const url = `${this.baseURL}/chats/${chatId}/stream`;
    const response = await fetch(url, { signal });
    await this.assertOk(response);
    yield* this.parseSSE(response);
  }

  async createChat(data: CreateChatRequest): Promise<Chat> {
    return this.request('/chats', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteChat(chatId: string): Promise<{ success: boolean }> {
    return this.request(`/chats/${chatId}`, {
      method: 'DELETE',
    });
  }

  async updateChat(
    chatId: string, 
    data: { title?: string; config?: ChatConfig }
  ): Promise<ChatWithMessages> {
    return this.request(`/chats/${chatId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async branchChat(
    chatId: string,
    messageId: string,
    title?: string
  ): Promise<ChatWithMessages> {
    return this.request(`/chats/${chatId}/branch`, {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId, title }),
    });
  }

  private async *parseSSE(response: Response): AsyncGenerator<StreamEvent> {
    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';
    let eventCount = 0;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.debug('[SSE] reader done (stream ended), events received:', eventCount);
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6);
            try {
              const event = JSON.parse(jsonStr) as StreamEvent;
              eventCount++;
              console.debug('[SSE] event #%d:', eventCount, event.type, event.type === 'message' ? (event.data as any)?.role : '');
              yield event;
              if (event.type === 'done') {
                console.debug('[SSE] done event received, total events:', eventCount);
                return;
              }
            } catch (e) {
              console.error('[SSE] Failed to parse SSE event:', jsonStr, e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  private async *streamPost(endpoint: string, body: Record<string, unknown>): AsyncGenerator<StreamEvent> {
    const url = `${this.baseURL}${endpoint}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    await this.assertOk(response);

    yield* this.parseSSE(response);
  }

  async *streamMessage(
    chatId: string,
    data: SendMessageRequest
  ): AsyncGenerator<StreamEvent> {
    yield* this.streamPost(`/chats/${chatId}/messages`, { ...data, stream: true });
  }

  async *streamRetry(chatId: string): AsyncGenerator<StreamEvent> {
    yield* this.streamPost(`/chats/${chatId}/retry`, { stream: true });
  }

  async *streamEdit(chatId: string, message: string): AsyncGenerator<StreamEvent> {
    yield* this.streamPost(`/chats/${chatId}/edit`, { message, stream: true });
  }

  // Configuration endpoints
  async listModels(): Promise<{ object: string; data: Model[] }> {
    return this.request('/config/models');
  }

  async listAgents(): Promise<{ agents: AgentConfig[] }> {
    return this.request('/config/agents');
  }

  async getDefaultChatConfig(workspaceId?: string | null): Promise<DefaultChatConfig> {
    const params = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : '';
    return this.request(`/config/default-chat${params}`);
  }

  // Tools endpoints
  async listTools(): Promise<{ tool_servers: ToolServer[] }> {
    return this.request('/tools');
  }

  // Skills endpoints
  async listSkills(): Promise<{ skills: Skill[] }> {
    return this.request('/skills');
  }

  async uploadFiles(files: File[]): Promise<FileResource[]> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const url = `${this.baseURL}/files`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    await this.assertOk(response);

    return response.json();
  }

  async deleteFile(fileId: string): Promise<{ status: string }> {
    return this.request(`/files/${fileId}`, {
      method: 'DELETE',
    });
  }

  // Connector endpoints
  async listConnectors(): Promise<{ connectors: Connector[] }> {
    return this.request('/connectors');
  }

  async listConnectorResources(connector: string): Promise<{ resources: ConnectorResource[] }> {
    const response = await this.request<{ repositories: ConnectorResource[] }>(`/connectors/repositories?connector=${encodeURIComponent(connector)}`);
    return { resources: response.repositories };
  }

  async browseConnectorTree(connector: string, resource: string, path: string = ""): Promise<FileNode> {
    return this.request(`/connectors/tree?connector=${encodeURIComponent(connector)}&repo=${encodeURIComponent(resource)}&path=${encodeURIComponent(path)}`);
  }

  async estimateConnectorTokens(connector: string, resource: string, paths: string[], excludePaths?: string[]): Promise<TokenEstimate> {
    return this.request(`/connectors/estimate?connector=${encodeURIComponent(connector)}`, {
      method: 'POST',
      body: JSON.stringify({ repo: resource, paths, exclude_paths: excludePaths || [] }),
    });
  }

  async uploadConnectorFiles(connector: string, resource: string, paths: string[], excludePaths?: string[]): Promise<FileResource[]> {
    return this.request(`/connectors/files?connector=${encodeURIComponent(connector)}`, {
      method: 'POST',
      body: JSON.stringify({ repo: resource, paths, exclude_paths: excludePaths || [] }),
    });
  }

  // Media endpoints
  async transcribeAudio(audioBlob: Blob): Promise<{ text: string }> {
    const formData = new FormData();
    formData.append('file', audioBlob, 'audio.webm');

    const url = `${this.baseURL}/media/transcribe`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    await this.assertOk(response);

    return response.json();
  }

  async generateSpeech(text: string): Promise<Blob> {
    const url = `${this.baseURL}/media/speech`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input: text }),
    });

    await this.assertOk(response);

    return response.blob();
  }

  async listWorkspaces(): Promise<{ workspaces: Workspace[] }> {
    return this.request('/workspaces');
  }

  async getWorkspace(id: string): Promise<Workspace> {
    return this.request(`/workspaces/${id}`);
  }

  async createWorkspace(data: { name: string; repo_url?: string | null; connector?: string }): Promise<Workspace> {
    return this.request('/workspaces', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteWorkspace(id: string): Promise<{ success: boolean }> {
    return this.request(`/workspaces/${id}`, {
      method: 'DELETE',
    });
  }

  async getWorkspaceTree(id: string, path: string = ""): Promise<FileNode> {
    return this.request(`/workspaces/${id}/tree?path=${encodeURIComponent(path)}`);
  }

  async getWorkspaceFile(id: string, path: string): Promise<string> {
    const url = `${this.baseURL}/workspaces/${id}/files/${path}`;
    const response = await fetch(url);

    await this.assertOk(response);

    return response.text();
  }

  async writeWorkspaceFile(id: string, path: string, content: string): Promise<{ success: boolean }> {
    return this.request(`/workspaces/${id}/files/${path}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    });
  }

  async createWorkspaceFile(id: string, path: string, content: string = ""): Promise<{ success: boolean }> {
    return this.request(`/workspaces/${id}/files/${path}`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  async deleteWorkspaceFile(id: string, path: string): Promise<{ success: boolean }> {
    return this.request(`/workspaces/${id}/files/${path}`, {
      method: 'DELETE',
    });
  }

  async renameWorkspaceFile(id: string, oldPath: string, newPath: string): Promise<{ success: boolean; new_path: string }> {
    return this.request(`/workspaces/${id}/files/${oldPath}`, {
      method: 'PATCH',
      body: JSON.stringify({ new_path: newPath }),
    });
  }

  async getWorkspaceFileList(id: string): Promise<string[]> {
    const result = await this.request<{ files: string[] }>(`/workspaces/${id}/ls`);
    return result.files;
  }

  async gitStatus(workspaceId: string): Promise<GitStatus> {
    return this.request(`/workspaces/${workspaceId}/git/status`);
  }

  async gitCommit(workspaceId: string, message: string): Promise<GitResult> {
    return this.request(`/workspaces/${workspaceId}/git/commit`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  async gitPull(workspaceId: string): Promise<GitResult> {
    return this.request(`/workspaces/${workspaceId}/git/pull`, {
      method: 'POST',
    });
  }

  async gitPush(workspaceId: string): Promise<GitResult> {
    return this.request(`/workspaces/${workspaceId}/git/push`, {
      method: 'POST',
    });
  }
}

export const api = new ApiClient();
